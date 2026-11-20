"""Общие функции для лабораторной работы «Гестурный пульт».

Все шаги лабораторной (step_01 ... step_10), самостоятельный трек A и
скрипт калибровки используют этот модуль. Здесь собраны:

* открытие камеры и обёртка над MediaPipe Hand Landmarker;
* рисование скелета кисти;
* показ окна и запись demo.gif;
* признаки пальцев, щипка и жестов;
* управление курсором и системной громкостью.
"""

import math
import subprocess
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image

pyautogui.PAUSE = 0

MODEL = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"

# Кости кисти: пары индексов точек, которые соединяются линиями.
LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
         (5, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15),
         (15, 16), (0, 17), (17, 18), (18, 19), (19, 20), (0, 9), (9, 13), (13, 17)]

# ---- Подобранные под руку пороги (обоснование — в отчёте) ----------------
ALPHA, DEAD_ZONE = 0.4, 2          # сглаживание курсора и зона покоя, px
PINCH_ON, PINCH_OFF = 0.45, 0.60   # гистерезис левого щипка (доли размера кисти)
VOL_MIN, VOL_MAX, VOL_STEP = 0.25, 1.05, 0.02
GESTURE_FRAMES = 4                 # сколько кадров держать жест для срабатывания

# Суставы PIP для четырёх пальцев (большой палец считаем отдельно).
FINGERS = [(5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)]


def open_camera(index=0):
    """Открывает камеру в 640x480. На Windows сначала пробуем DirectShow."""
    if sys.platform == "win32":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return cap


class Tracker:
    """Hand Landmarker в режиме VIDEO: кадр + монотонная метка времени."""

    def __init__(self):
        if not MODEL.exists():
            raise SystemExit(f"Модель не найдена: {MODEL}")
        self.ts = 0
        # Путь с кириллицей C++-часть MediaPipe не открывает, поэтому
        # передаём модель байтами: так проект работает из любой папки.
        self.lm = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=MODEL.read_bytes()),
            running_mode=vision.RunningMode.VIDEO, num_hands=1))

    def __call__(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # В режиме VIDEO метка времени обязана строго возрастать.
        self.ts = max(int(time.monotonic() * 1000), self.ts + 1)
        res = self.lm.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self.ts)
        return res.hand_landmarks[0] if res.hand_landmarks else None


def draw(frame, pts):
    """Рисует скелет из 21 точки."""
    h, w = frame.shape[:2]
    px = [(int(p.x * w), int(p.y * h)) for p in pts]
    for a, b in LINKS:
        cv2.line(frame, px[a], px[b], (255, 180, 0), 2)
    for x, y in px:
        cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)


class Recorder:
    """Запись demo.gif по клавише r (шаг 10)."""

    def __init__(self):
        self.on, self.buf, self.i = False, [], 0

    def add(self, frame):
        if self.on:
            cv2.circle(frame, (620, 20), 8, (0, 0, 255), -1)
            if self.i % 3 == 0:
                small = cv2.resize(frame, (480, 360))
                self.buf.append(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
            self.i += 1

    def toggle(self):
        self.on = not self.on
        if not self.on and self.buf:
            out = Path(__file__).resolve().parent / "demo.gif"
            self.buf[0].save(out, save_all=True, append_images=self.buf[1:],
                             duration=100, loop=0)
            print("Сохранено:", out)
            self.buf = []


rec = Recorder()


def show(title, frame):
    """Показывает кадр, обрабатывает r (запись) и возвращает код клавиши."""
    rec.add(frame)
    cv2.imshow(title, frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('r') or (key == ord('q') and rec.on):
        rec.toggle()
    return key


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def fingers_up(pts):
    """Счёт выпрямленных пальцев по расстоянию кончика от запястья.

    Запас 15% не даёт пальцу мигать, когда он на границе.
    """
    tips, joints = (4, 8, 12, 16, 20), (3, 6, 10, 14, 18)
    return [dist(pts[t], pts[0]) > 1.15 * dist(pts[j], pts[0])
            for t, j in zip(tips, joints, strict=True)]


def pinch_strength(pts):
    """Расстояние большого и указательного пальцев в размерах кисти."""
    return dist(pts[4], pts[8]) / max(dist(pts[0], pts[9]), 1e-6)


def pinch_level(pts):
    """Щипок, переведённый в 0..1 для громкости."""
    return min(max((pinch_strength(pts) - VOL_MIN) / (VOL_MAX - VOL_MIN), 0.0), 1.0)


def set_volume(level):
    """Системная громкость 0..1. Команда зависит от ОС."""
    level = min(max(float(level), 0.0), 1.0)
    pct = round(level * 100)
    if sys.platform == "win32":
        try:
            from pycaw.pycaw import AudioUtilities
            AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(level, None)
        except Exception as exc:  # noqa: BLE001 — нет pycaw, нет устройства и т.п.
            print(f"Громкость недоступна: {exc}")
    elif sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f"set volume output volume {pct}"],
                       check=False)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                       check=False)


class Cursor:
    """Курсор за точкой 5, EMA-сглаживание, клик по щипку с гистерезисом."""

    def __init__(self):
        self.size = pyautogui.size()
        self.ema = self.last = None
        self.down = False

    def update(self, pts):
        x, y = pts[5].x, pts[5].y
        if self.ema is not None:
            x = self.ema[0] + ALPHA * (x - self.ema[0])
            y = self.ema[1] + ALPHA * (y - self.ema[1])
        self.ema = (x, y)
        p = (int(x * self.size[0]), int(y * self.size[1]))
        if self.last is None or max(abs(p[0] - self.last[0]),
                                    abs(p[1] - self.last[1])) >= DEAD_ZONE:
            pyautogui.moveTo(*p)
            self.last = p
        fist = not any(fingers_up(pts)[1:])
        pinch = pinch_strength(pts)
        if not self.down and not fist and pinch < PINCH_ON:
            self.down = True
            pyautogui.mouseDown()
        elif self.down and (fist or pinch > PINCH_OFF):
            self.down = False
            pyautogui.mouseUp()

    def release(self):
        if self.down:
            pyautogui.mouseUp()
            self.down = False
        self.ema = self.last = None


def angle_at(a, b, c):
    """Угол в точке b (градусы) между лучами b->a и b->c."""
    v1, v2 = (a.x - b.x, a.y - b.y), (c.x - b.x, c.y - b.y)
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / max(
        math.hypot(*v1) * math.hypot(*v2), 1e-6)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def finger_states(pts, thr=160.0):
    """Выпрямленность четырёх пальцев по углу в суставе PIP."""
    return [angle_at(pts[m], pts[p], pts[t]) > thr for m, p, t in FINGERS]


def gesture(pts, thr=160.0):
    """FIST / PALM / GUN / None. Углы не зависят от поворота кисти."""
    s = finger_states(pts, thr)
    if not any(s):
        return "FIST"
    if all(s):
        return "PALM"
    if s[0] and not any(s[1:]):
        return "GUN"
    return None


class Hold:
    """Жест срабатывает один раз, если удержан need кадров подряд."""

    def __init__(self, need=GESTURE_FRAMES):
        self.need = need
        self.reset()

    def reset(self):
        self.g, self.n = None, 0

    def update(self, g):
        self.n = self.n + 1 if g and g == self.g else 1
        self.g = g
        return g if g and self.n == self.need else None


def draw_hint(frame, text, y=None):
    """Мелкая подсказка внизу окна (только латиница: cv2 не умеет кириллицу)."""
    h = frame.shape[0]
    cv2.putText(frame, text, (10, (y if y is not None else h - 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
