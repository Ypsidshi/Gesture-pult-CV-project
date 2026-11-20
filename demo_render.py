"""Рендер demo.gif и скриншотов без камеры.

Скрипт подменяет pyautogui заглушкой и подаёт в настоящие функции из
common.py / track_A_control.py синтетическую кисть из hand_model.py.
Получается тот же интерфейс, что и в живом приложении, но сценарий
воспроизводится детерминированно.

Запуск:  python demo_render.py
Результат: demo.gif, demo_track_A.gif, screenshots/*.png
"""

import itertools
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import common
import hand_model as hm
import track_A_control as track

ROOT = Path(__file__).resolve().parent
W, H, FPS = 640, 480, 30
GIF_EVERY = 2  # каждый второй кадр -> 15 кадров/с в gif


# --------------------------------------------------------------------------
# Заглушка pyautogui
# --------------------------------------------------------------------------
class FakeGui:
    def __init__(self):
        self.now = 0.0
        self.events = []
        self.calls = []
        self.vol = 0.0

    def size(self):
        return (1920, 1080)

    def _log(self, text):
        if not self.events or self.events[-1][1] != text:
            self.events.append((self.now, text))
            self.events = self.events[-4:]

    def moveTo(self, x, y):
        pass

    def mouseDown(self, button="left"):
        self.calls.append(("down", button))
        self._log("ЛКМ ↓")

    def mouseUp(self, button="left"):
        self.calls.append(("up", button))
        self._log("ЛКМ ↑")

    def click(self, x=None, y=None, button="left", clicks=1):
        self.calls.append(("click", button))
        self._log("ПКМ" if button == "right" else "ЛКМ")

    def doubleClick(self, x=None, y=None, button="left"):
        self.calls.append(("double", button))
        self._log("2× клик")

    def scroll(self, units):
        self.calls.append(("scroll", units))
        self._log("колесо ↑" if units > 0 else "колесо ↓")

    def press(self, key):
        self.calls.append(("press", key))
        self._log({"right": "слайд →", "left": "слайд ←", "space": "пауза"}.get(key, key))

    def set_volume(self, level):
        self.vol = float(level)
        self._log(f"громкость {level:.0%}")


fake = FakeGui()
common.pyautogui = fake
track.pyautogui = fake
common.set_volume = fake.set_volume


# --------------------------------------------------------------------------
# Шрифты и текст
# --------------------------------------------------------------------------
def _font_path(bold=False):
    names = (["seguisb.ttf", "arialbd.ttf", "segoeuib.ttf"] if bold
             else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return str(path)
    return "DejaVuSans.ttf"


_FONTS = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(_font_path(bold), size)
    return _FONTS[key]


def put_texts(frame, labels):
    """labels: (текст, x, y, размер, цвет BGR, anchor, bold)."""
    if not labels:
        return frame
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    for item in labels:
        text, x, y, size, color = item[:5]
        anchor = item[5] if len(item) > 5 else "la"
        bold = item[6] if len(item) > 6 else False
        draw.text((x, y), text, font=font(size, bold),
                  fill=(color[2], color[1], color[0]), anchor=anchor)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------
# Фон и простые элементы
# --------------------------------------------------------------------------
def make_background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    top = np.array([42, 37, 33], np.float32)      # BGR
    bottom = np.array([22, 20, 19], np.float32)
    u = (yy / (H - 1))[..., None]
    bg = top * (1 - u) + bottom * u
    # мягкая виньетка, без ярких пятен: так gif меньше и чище
    d2 = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    bg *= np.clip(1.04 - 0.22 * d2, 0.55, 1.0)[..., None]
    return np.clip(bg, 0, 255).astype(np.uint8)


BG = make_background()


def panel(frame, x1, y1, x2, y2, color=(38, 34, 31), alpha=0.88,
          border=(90, 80, 72), bw=2):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    if bw:
        cv2.rectangle(frame, (x1, y1), (x2, y2), border, bw)
    return frame


def draw_cursor(frame, cx, cy, scale=0.9):
    pts = np.array([(0, 0), (0, 20), (5, 15), (9, 23), (13, 21), (9, 13),
                    (16, 13)], np.float32) * scale
    pts[:, 0] += cx
    pts[:, 1] += cy
    cv2.fillPoly(frame, [pts.astype(np.int32)], (255, 255, 255))
    cv2.polylines(frame, [pts.astype(np.int32)], True, (20, 20, 20), 2)


def draw_folder(frame, cx, cy, size=28):
    x1, y1 = int(cx - size), int(cy - size * 0.7)
    x2, y2 = int(cx + size), int(cy + size * 0.8)
    cv2.rectangle(frame, (x1, y1 + 6), (x1 + 18, y1 + 12), (50, 160, 230), -1)
    cv2.rectangle(frame, (x1, y1 + 10), (x2, y2), (70, 185, 245), -1)
    cv2.rectangle(frame, (x1, y1 + 10), (x2, y2), (35, 120, 180), 1)
    cv2.line(frame, (x1, y1 + 18), (x2, y1 + 18), (120, 215, 255), 1)


def draw_slide(frame, number, total=6):
    x1, y1, x2, y2 = 84, 96, 556, 402
    cv2.rectangle(frame, (x1 + 5, y1 + 7), (x2 + 5, y2 + 7), (10, 10, 10), -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (245, 245, 245), -1)
    cv2.rectangle(frame, (x1, y1), (x2, y1 + 8), (200, 120, 40), -1)
    return [(f"Слайд {number}", x1 + 34, y1 + 34, 26, (30, 30, 30), "la", True),
            ("Гестурный пульт", x1 + 34, y1 + 76, 18, (70, 70, 70), "la", False),
            ("•  MediaPipe Hand Landmarker — 21 точка", x1 + 34, y1 + 128, 15,
             (60, 60, 60), "la", False),
            ("•  Жесты по углам, а не по расстояниям", x1 + 34, y1 + 160, 15,
             (60, 60, 60), "la", False),
            ("•  Гистерезис и антидребезг", x1 + 34, y1 + 192, 15,
             (60, 60, 60), "la", False),
            (f"{number} / {total}", x2 - 34, y2 - 24, 13, (120, 120, 120), "ra", False)]


def draw_volume_card(frame, level):
    x1, y1, x2, y2 = 436, 126, 612, 360
    panel(frame, x1, y1, x2, y2, (44, 40, 36), 0.92)
    # динамик
    cv2.rectangle(frame, (x1 + 20, y1 + 44), (x1 + 30, y1 + 60), (210, 210, 210), -1)
    cv2.fillPoly(frame, [np.array([(x1 + 30, y1 + 44), (x1 + 46, y1 + 32),
                                   (x1 + 46, y1 + 72), (x1 + 30, y1 + 60)], np.int32)],
                 (210, 210, 210))
    tx = x2 - 32
    cv2.rectangle(frame, (tx - 6, y1 + 28), (tx + 6, y2 - 34), (28, 26, 24), -1)
    top, bottom = y1 + 32, y2 - 38
    knob = int(bottom + (top - bottom) * level)
    cv2.rectangle(frame, (tx - 6, knob), (tx + 6, bottom), (0, 190, 255), -1)
    cv2.circle(frame, (tx, knob), 10, (255, 255, 255), -1)
    cv2.circle(frame, (tx, knob), 10, (80, 80, 80), 2)
    return [(f"{level:.0%}", x1 + 22, y1 + 100, 34, (255, 255, 255), "la", True),
            ("Громкость", x1 + 22, y1 + 146, 14, (190, 185, 180), "la", False),
            ("щипок", x1 + 22, y1 + 176, 13, (140, 135, 130), "la", False)]


def draw_context_menu(frame, x, y):
    w, h = 176, 132
    x = min(x, W - w - 8)
    y = min(y, H - h - 8)
    cv2.rectangle(frame, (x + 4, y + 5), (x + w + 4, y + h + 5), (10, 10, 10), -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (250, 250, 250), -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (190, 190, 190), 1)
    cv2.rectangle(frame, (x + 2, y + 4), (x + w - 2, y + 32), (225, 238, 250), -1)
    for i in range(1, 4):
        yy = y + 6 + i * 30
        cv2.line(frame, (x + 8, yy), (x + w - 8, yy), (225, 225, 225), 1)
    return [(t, x + 14, y + 10 + i * 30, 13, (35, 35, 35), "la", False)
            for i, t in enumerate(("Открыть", "Создать", "Обновить", "Параметры"))]


def draw_scroll_page(frame, offset, total=18):
    x1, y1, x2, y2 = 66, 92, 560, 404
    panel(frame, x1, y1, x2, y2, (245, 245, 245), 1.0, (200, 200, 200), 1)
    cv2.rectangle(frame, (x1, y1), (x2, y1 + 28), (225, 225, 225), -1)
    cv2.circle(frame, (x1 + 16, y1 + 14), 4, (235, 90, 80), -1)
    cv2.circle(frame, (x1 + 30, y1 + 14), 4, (240, 190, 70), -1)
    cv2.circle(frame, (x1 + 44, y1 + 14), 4, (100, 190, 110), -1)
    labels = []
    for i in range(14):
        line = i + int(offset)
        y = y1 + 48 + i * 20
        if y > y2 - 16:
            break
        labels.append((f"{line + 1:02d}  строка текста для проверки прокрутки",
                       x1 + 18, y, 11, (70, 70, 70), "la", False))
    # полоса прокрутки
    sx = x2 - 12
    cv2.rectangle(frame, (sx, y1 + 34), (sx + 5, y2 - 10), (215, 215, 215), -1)
    kh = 86
    ky = y1 + 36 + int(min(max(offset / total, 0), 1) * (y2 - y1 - 130))
    cv2.rectangle(frame, (sx, ky), (sx + 5, ky + kh), (130, 130, 130), -1)
    return labels


def draw_folder_window(frame):
    x1, y1, x2, y2 = 150, 128, 494, 382
    panel(frame, x1, y1, x2, y2, (242, 242, 242), 1.0, (190, 190, 190), 1)
    cv2.rectangle(frame, (x1, y1), (x2, y1 + 30), (228, 228, 228), -1)
    labels = [("Новая папка", x1 + 14, y1 + 8, 12, (40, 40, 40), "la", True)]
    for i in range(3):
        for j in range(2):
            cx = x1 + 48 + j * 118
            cy = y1 + 78 + i * 72
            draw_folder(frame, cx, cy, 17)
            labels.append((f"файл_{i * 2 + j + 1}", cx, cy + 28, 10,
                           (50, 50, 50), "ma", False))
    return labels


def draw_desktop(frame, icon, pressed=False):
    labels = []
    x, y = int(icon[0] * W), int(icon[1] * H)
    draw_folder(frame, x, y, 22)
    if pressed:
        cv2.rectangle(frame, (x - 30, y - 24), (x + 30, y + 30),
                      (255, 255, 255), 1)
    labels.append(("Проект", x, y + 30, 11, (235, 235, 235), "ma", False))
    return labels


def draw_action_chips(frame, events, t):
    labels = []
    shown = [(ts, txt) for ts, txt in events if t - ts < 2.2][-3:]
    for i, (_, txt) in enumerate(shown):
        y = H - 30 - (len(shown) - 1 - i) * 28
        bw = int(len(txt) * 7.4 + 22)
        x1 = W - bw - 14
        cv2.rectangle(frame, (x1, y - 5), (x1 + bw, y + 21), (30, 28, 26), -1)
        cv2.rectangle(frame, (x1, y - 5), (x1 + bw, y + 21), (255, 190, 60), 1)
        labels.append((txt, x1 + 11, y, 13, (255, 220, 120), "la", False))
    return labels


def draw_status(frame, mode, color, line2="", fist_n=0):
    panel(frame, 0, 0, W, 52, (20, 18, 16), 0.65, (0, 0, 0), 0)
    cv2.rectangle(frame, (0, 0), (6, 52), color, -1)
    labels = [("ГЕСТУРНЫЙ ПУЛЬТ", 18, 14, 17, (245, 245, 245), "la", True),
              (mode, W - 18, 14, 20, color, "ra", True)]
    if line2:
        labels.append((line2, 18, 56, 13, (220, 220, 220), "la", False))
    if fist_n:
        labels.append((f"FIST {fist_n}/8", W - 18, 60, 12, (90, 90, 255), "ra", True))
    return labels


def draw_title_card(frame, title, subtitle):
    panel(frame, 92, 168, 548, 318, (26, 23, 21), 0.93, (150, 125, 80), 2)
    cv2.rectangle(frame, (92, 168), (548, 174), (0, 190, 255), -1)
    return [(title, W / 2, 200, 25, (245, 245, 245), "ma", True),
            (subtitle, W / 2, 246, 13, (215, 205, 190), "ma", False),
            ("синтетический рендер интерфейса", W / 2, 286, 10,
             (150, 145, 140), "ma", False)]


# --------------------------------------------------------------------------
# Таймлайн поз
# --------------------------------------------------------------------------
class Timeline:
    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k[0])

    @staticmethod
    def resolve(desc):
        if desc is None:
            return None
        if isinstance(desc, tuple) and desc[0] == "pinch":
            return hm.pinch_pose(desc[1])
        return hm.pose(desc)

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            k = ks[0]
            pts = self.resolve(k[1])
            return hm.place(pts, (k[2], k[3]), k[4]) if pts else None
        if t >= ks[-1][0]:
            k = ks[-1]
            pts = self.resolve(k[1])
            return hm.place(pts, (k[2], k[3]), k[4]) if pts else None
        for a, b in itertools.pairwise(ks):
            if a[0] <= t <= b[0]:
                u = (t - a[0]) / max(b[0] - a[0], 1e-6)
                u = u * u * (3 - 2 * u)
                pa, pb = self.resolve(a[1]), self.resolve(b[1])
                if pa is None or pb is None:
                    src = pb if u > 0.5 else pa
                    if src is None:
                        return None
                    x = a[2] + (b[2] - a[2]) * u
                    y = a[3] + (b[3] - a[3]) * u
                    return hm.place(src, (x, y), a[4])
                pts = hm.blend(pa, pb, u)
                return hm.place(pts, (a[2] + (b[2] - a[2]) * u,
                                      a[3] + (b[3] - a[3]) * u),
                                a[4] + (b[4] - a[4]) * u)
        return None


MAIN_KEYS = [
    (0.0, None, 0.55, 0.70, 1.1),
    (0.9, "palm", 0.55, 0.70, 1.1),
    (1.8, "palm", 0.35, 0.45, 1.1),
    (2.1, "palm", 0.35, 0.45, 1.1),
    (2.3, ("pinch", 0.95), 0.36, 0.46, 1.1),
    (2.8, ("pinch", 0.95), 0.47, 0.57, 1.1),
    (3.0, ("pinch", 0.0), 0.48, 0.58, 1.1),
    (3.3, "fist", 0.50, 0.60, 1.1),
    (3.9, "fist", 0.50, 0.60, 1.1),
    (4.1, ("pinch", 0.0), 0.52, 0.62, 1.1),
    (4.9, ("pinch", 1.0), 0.52, 0.62, 1.1),
    (5.7, ("pinch", 0.0), 0.52, 0.62, 1.1),
    (6.4, ("pinch", 0.8), 0.52, 0.62, 1.1),
    (7.0, ("pinch", 0.3), 0.52, 0.62, 1.1),
    (7.5, "fist", 0.52, 0.62, 1.1),
    (8.1, "fist", 0.52, 0.62, 1.1),
    (8.3, "palm", 0.52, 0.62, 1.1),
    (8.7, "palm", 0.52, 0.62, 1.1),
    (8.9, "gun", 0.52, 0.62, 1.1),
    (9.5, "gun", 0.52, 0.62, 1.1),
    (9.7, "palm", 0.52, 0.62, 1.1),
    (10.3, "palm", 0.52, 0.62, 1.1),
    (10.5, "fist", 0.52, 0.62, 1.1),
    (11.1, "fist", 0.52, 0.62, 1.1),
    (11.3, None, 0.55, 0.66, 1.1),
]

TRACK_KEYS = [
    (0.0, None, 0.55, 0.70, 1.1),
    (0.8, "palm", 0.55, 0.70, 1.1),
    (1.5, "palm", 0.38, 0.47, 1.1),
    (1.9, "palm", 0.38, 0.47, 1.1),
    (2.1, "right_pinch", 0.38, 0.47, 1.1),
    (2.9, "right_pinch", 0.38, 0.47, 1.1),
    (3.1, "palm", 0.40, 0.49, 1.1),
    (3.8, "palm", 0.56, 0.62, 1.1),
    (4.3, "two", 0.56, 0.62, 1.1),
    (4.9, "two", 0.56, 0.53, 1.1),
    (5.5, "two", 0.56, 0.66, 1.1),
    (6.1, "two", 0.56, 0.51, 1.1),
    (6.6, "two", 0.56, 0.62, 1.1),
    (6.9, "palm", 0.56, 0.62, 1.1),
    (7.4, "palm", 0.38, 0.47, 1.1),
    (7.7, ("pinch", 0.95), 0.38, 0.47, 1.1),
    (7.8, ("pinch", 0.95), 0.38, 0.47, 1.1),
    (8.0, ("pinch", 0.0), 0.38, 0.47, 1.1),
    (8.35, ("pinch", 0.95), 0.38, 0.47, 1.1),
    (8.45, ("pinch", 0.95), 0.38, 0.47, 1.1),
    (8.65, ("pinch", 0.0), 0.38, 0.47, 1.1),
    (9.4, "palm", 0.55, 0.62, 1.1),
    (10.0, None, 0.55, 0.66, 1.1),
]


# --------------------------------------------------------------------------
# Рендер основного демо
# --------------------------------------------------------------------------
def render_main():
    fake.calls.clear()
    fake.events.clear()
    tl = Timeline(MAIN_KEYS)
    cur, hold = common.Cursor(), common.Hold()
    modes = ["CURSOR", "VOLUME", "SLIDES"]
    mode_i, fist_n, vol = 0, 0, 0.0
    slide = 2
    icon = np.array([0.30, 0.30])
    icons = {"pos": icon, "pressed": False}
    frames, shots = [], {}
    n = int(11.6 * FPS)

    for i in range(n):
        t = i / FPS
        fake.now = t
        pts = tl.at(t)
        frame = BG.copy()
        labels = []

        mode = modes[mode_i]
        color = track.COLOR.get(mode, (0, 255, 0))
        g = None

        if pts:
            g = common.gesture(pts)
            if g == "FIST":
                fist_n += 1
            else:
                if fist_n >= 8:
                    mode_i = (mode_i + 1) % len(modes)
                    cur.release()
                    hold.reset()
                fist_n = 0
            mode = modes[mode_i]
            color = track.COLOR[mode]

            if mode == "CURSOR":
                cur.update(pts)
                if cur.down:
                    # иконка тянется за курсором, если щипок начался рядом
                    cx, cy = pts[5].x * W, pts[5].y * H
                    if abs(cx - icons["pos"][0] * W) < 90 and abs(cy - icons["pos"][1] * H) < 90:
                        icons["pos"] = np.array([pts[5].x, pts[5].y])
                icons["pressed"] = cur.down
            elif mode == "VOLUME" and g != "FIST":
                level = common.pinch_level(pts)
                if abs(level - vol) >= common.VOL_STEP:
                    common.set_volume(level)
                    vol = level
            elif mode == "SLIDES":
                k = hold.update(g)
                if k == "PALM":
                    slide = min(slide + 1, 6)
                    fake.press("right")
                elif k == "GUN":
                    slide = max(slide - 1, 1)
                    fake.press("left")

        else:
            cur.release()
            hold.reset()
            fist_n = 0

        mode = modes[mode_i]
        color = track.COLOR[mode]

        # ---- сцена
        card = t < 0.9 or t > 11.15
        if not card and mode == "SLIDES":
            labels += draw_slide(frame, slide)
        elif not card:
            labels += draw_desktop(frame, tuple(icons["pos"]), icons["pressed"])
        if mode == "VOLUME" and not card:
            labels += draw_volume_card(frame, vol)

        if pts:
            common.draw(frame, pts)
            if mode in ("CURSOR", "VOLUME"):
                draw_cursor(frame, int(pts[5].x * W), int(pts[5].y * H))

        labels += draw_status(frame, mode, color,
                              f"слайд {slide}/6" if mode == "SLIDES"
                              else f"click {int(cur.down)}   vol {vol:.0%}",
                              min(fist_n, 8))
        labels += draw_action_chips(frame, fake.events, t) if mode != "SLIDES" else []
        if t < 0.9:
            labels += draw_title_card(frame, "Гестурный пульт",
                                      "щипок — клик · щипок — громкость · жесты — слайды")
        if t > 11.15:
            labels += draw_title_card(frame, "Демонстрация завершена",
                                      "r — запись demo.gif · q — выход")

        cv2.rectangle(frame, (0, 0), (W - 1, H - 1), color, 6)
        frame = put_texts(frame, labels)

        if i % GIF_EVERY == 0:
            frames.append(frame)
        for key, t_snap in (("cursor", 2.05), ("drag", 2.6), ("volume", 5.6),
                            ("slides", 8.5), ("fist", 3.6)):
            if i == round(t_snap * FPS):
                shots[key] = frame.copy()

    save_gif(frames, ROOT / "demo.gif")
    for name, img in shots.items():
        Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(
            ROOT / "screenshots" / f"{name}.png")
    return shots


# --------------------------------------------------------------------------
# Рендер демо трека A
# --------------------------------------------------------------------------
def render_track():
    fake.calls.clear()
    fake.events.clear()
    tl = Timeline(TRACK_KEYS)
    ctrl = track.ControlMouse()
    icon = (0.30, 0.30)
    menu_t = 0.0
    folder_t = 0.0
    prev_status = ""
    scroll_pos = 0.0
    last_scroll = 0
    frames, shots = [], {}
    n = int(10.0 * FPS)

    for i in range(n):
        t = i / FPS
        fake.now = t
        pts = tl.at(t)
        frame = BG.copy()
        labels = []

        if pts:
            ctrl.update(pts, now=t)
            if ctrl.status != prev_status:
                prev_status = ctrl.status
                if ctrl.status == "RMB":
                    menu_t = t
                if ctrl.status == "DOUBLE":
                    folder_t = t
            scrolls = [c for c in fake.calls if c[0] == "scroll"]
            if len(scrolls) != last_scroll:
                last_scroll = len(scrolls)
                scroll_pos = min(max(scroll_pos - scrolls[-1][1] * 0.35, 0), 16)

        mode = "CONTROL"
        color = track.COLOR[mode]
        card = t < 0.75 or t > 9.5

        if not card:
            labels += draw_desktop(frame, icon)
        labels += draw_status(frame, mode, color,
                              f"статус: {ctrl.status}", 0)

        # фон действий — до кисти, чтобы скелет оставался поверх
        if 4.0 < t < 7.0 and not card:
            labels += draw_scroll_page(frame, scroll_pos)
        if 0 < t - folder_t < 2.4 and not card:
            labels += draw_folder_window(frame)

        if pts and not card:
            common.draw(frame, pts)
            draw_cursor(frame, int(pts[5].x * W), int(pts[5].y * H))

        # контекстное меню — поверх кисти, как настоящее окно
        if 0 < t - menu_t < 1.2 and not card:
            mx = int(0.42 * W)
            my = int(0.36 * H)
            labels += draw_context_menu(frame, mx, my)

        labels += draw_action_chips(frame, fake.events, t)
        cv2.rectangle(frame, (0, 0), (W - 1, H - 1), color, 6)

        if t < 0.75:
            labels += draw_title_card(frame, "Трек A. Управление",
                                      "правый клик · прокрутка · двойной клик")
        if t > 9.5:
            labels += draw_title_card(frame, "Трек A выполнен",
                                      "CONTROL: ПКМ, колесо, двойной клик")

        # подписи сценария
        if 1.6 < t < 2.0:
            labels.append(("щипок большой + средний → ПКМ", 18, 74, 15,
                           (255, 220, 120), "la", True))
        elif 4.2 < t < 6.8:
            labels.append(("два пальца + движение кисти → колесо", 18, 74, 15,
                           (255, 220, 120), "la", True))
        elif 7.3 < t < 8.9:
            labels.append(("два быстрых щипка → двойной клик", 18, 74, 15,
                           (255, 220, 120), "la", True))

        frame = put_texts(frame, labels)
        if i % GIF_EVERY == 0:
            frames.append(frame)
        for key, t_snap in (("right_click", 2.4), ("scroll", 5.2),
                            ("double_click", 8.4)):
            if i == round(t_snap * FPS):
                shots[key] = frame.copy()

    save_gif(frames, ROOT / "demo_track_A.gif")
    for name, img in shots.items():
        Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(
            ROOT / "screenshots" / f"{name}.png")
    return shots


def save_gif(frames, path):
    if not frames:
        return
    rgb = [Image.fromarray(cv2.cvtColor(cv2.resize(f, (480, 360)),
                                       cv2.COLOR_BGR2RGB)) for f in frames]
    palette = rgb[0].quantize(colors=64, method=Image.MEDIANCUT)
    frames_p = [f.quantize(palette=palette, dither=Image.NONE) for f in rgb]
    frames_p[0].save(path, save_all=True, append_images=frames_p[1:],
                     duration=70, loop=0, optimize=True, disposal=2)
    print("Сохранено:", path, f"({len(frames_p)} кадров, {path.stat().st_size / 1e6:.1f} МБ)")


def main():
    (ROOT / "screenshots").mkdir(exist_ok=True)
    fake.calls.clear()
    render_main()
    fake.calls.clear()
    render_track()


if __name__ == "__main__":
    main()
