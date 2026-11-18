"""Единый графический пульт для лабораторной № 4.

Запускает шаги 1–10, трек A, калибровку и автотесты по очереди,
показывает инструкцию к текущему шагу и ведёт журнал выполнения.
Сами шаги остаются отдельными .py-файлами: пульт запускает их через
subprocess и ждёт завершения (в окне шага нужно нажать q).

Запуск:  python gesture_hub.py
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "hub_state.json"
MODEL = ROOT / "models" / "hand_landmarker.task"

# ---- палитра ---------------------------------------------------------------
BG = "#14110e"
PANEL = "#1d1916"
PANEL2 = "#27211c"
BORDER = "#3a3028"
TEXT = "#f3ede5"
MUTED = "#a99d8f"
ACCENT = "#ffc247"
GREEN = "#63d69a"
RED = "#ff7a7a"
BLUE = "#68c7ff"

CORE = 10          # шаги 1–10, они считаются в прогресс-баре


@dataclass(frozen=True)
class Step:
    sid: str
    title: str
    script: str
    summary: str
    do: str
    keys: str
    check: str
    warning: str = ""
    extra: bool = False

    @property
    def window(self) -> str:
        """Заголовок окна OpenCV, которое надо показать поверх остальных."""
        if self.sid == "A":
            return "track_A"
        if self.sid == "K":
            return "calibration"
        if self.sid == "T":
            return ""
        return f"step_{int(self.sid):02d}"


STEPS = [
    Step(
        "1", "Камера и FPS", "step_01_camera.py",
        "Проверяем камеру: зеркальный кадр 640×480 и частоту 25–30 кадров/с.",
        "Запустите шаг и посмотрите на окно. Кадр должен быть зеркальным, "
        "без заметной задержки. В левом верхнем углу показывается FPS.",
        "q — завершить шаг",
        "FPS 25–30, картинка плавная.",
    ),
    Step(
        "2", "21 точка кисти", "step_02_landmarks.py",
        "MediaPipe Hand Landmarker строит скелет кисти из 21 точки.",
        "Покажите руку в кадре. Точки должны лежать на суставах, линии — "
        "по пальцам. Проверьте скелет при повороте и наклоне кисти.",
        "q — завершить шаг",
        "Скелет не рассыпается, при уходе руки исчезает.",
    ),
    Step(
        "3", "Счёт пальцев", "step_03_fingers.py",
        "Выпрямленные пальцы считаются по расстоянию кончика от запястья.",
        "Покажите 0, 1, 3 и 5 пальцев. Отдельно проверьте «козу» — "
        "должно получиться 2. Число выводится крупно в центре кадра.",
        "q — завершить шаг",
        "0, 1, 3, 5 и «коза» = 2.",
    ),
    Step(
        "4", "Курсор и щипок-клик", "step_04_cursor.py",
        "Курсор идёт за точкой 5, сглаживается EMA и кликает по щипку.",
        "Подвигайте рукой — курсор должен плавно следовать за ней. "
        "Сомкните большой и указательный пальцы — это ЛКМ, разожмите — "
        "отпускание. Курсор лучше держать над пустым местом.",
        "q — завершить шаг",
        "Нет дрожания; в кулаке клик не срабатывает.",
        warning="Шаг управляет реальной мышью: клики настоящие.",
    ),
    Step(
        "5", "Громкость", "step_05_volume.py",
        "Режимы IDLE / VOLUME / CURSOR: громкость задаёт расстояние в щипке.",
        "Покажите один палец — включится VOLUME, сведите и разведите "
        "большой и указательный. Ладонь — CURSOR, кулак — IDLE. "
        "В окне видны режим и текущая громкость.",
        "q — завершить шаг",
        "Громкость меняется плавно, курсор в кулаке замирает.",
        warning="Шаг меняет системную громкость.",
    ),
    Step(
        "6", "Гистерезис и антидребезг", "step_06_debounce.py",
        "Сравниваем raw_flips и deb_flips при медленном щипке.",
        "Медленно смыкайте и размыкайте щипок 10–15 раз. Смотрите на два "
        "счётчика: у сырого порога переключений должно быть заметно больше, "
        "чем у гистерезиса с подтверждением.",
        "q — завершить шаг",
        "deb_flips меньше raw_flips в несколько раз.",
    ),
    Step(
        "7", "Жесты FIST / PALM / GUN", "step_07_gestures.py",
        "Жесты определяются по углам PIP и не зависят от поворота кисти.",
        "Покажите кулак, ладонь и «пистолет». Держите позу: после "
        "GESTURE_FRAMES кадров появится надпись FIRED.",
        "q — завершить шаг",
        "Рамка и FIRED совпадают с жестом, переходные позы не срабатывают.",
    ),
    Step(
        "8", "Слайды", "step_08_slides.py",
        "PALM → right, GUN → left, FIST → space; жест срабатывает один раз.",
        "Откройте презентацию и щёлкните по ней, чтобы она была активной. "
        "Показывайте ладонь, «пистолет» и кулак. Окно камеры можно оставить "
        "поверх, но фокус клавиатуры — на презентации.",
        "q — в окне камеры (сначала щёлкните по нему)",
        "Слайды листаются без повторов и лишних нажатий.",
        warning="Шаг нажимает реальные клавиши в активном окне.",
    ),
    Step(
        "9", "Итоговый пульт", "step_09_final.py",
        "CURSOR / VOLUME / SLIDES, переключение кулаком или клавишами 1–3.",
        "Кулак, удержанный 40 кадров (~1,3 с), переключает режим. Клавиши 1–3 "
        "выбирают режим сразу. В CURSOR работает щипок-клик, в VOLUME — "
        "громкость, в SLIDES — ладонь и «пистолет».",
        "1–3 — режим, r — запись, q — выход",
        "Режимы переключаются без случайных кликов.",
        warning="Шаг управляет мышью, громкостью и клавишами.",
    ),
    Step(
        "10", "Запись demo.gif", "step_10_demo.py",
        "Финальный пульт пишет ролик по клавише r.",
        "Запустите, нажмите r, покажите сценарий 20–30 секунд и снова r. "
        "Файл demo.gif сохранится рядом со скриптом. При q запись тоже "
        "сохраняется.",
        "r — старт/стоп записи, 1–3 — режим, q — выход",
        "demo.gif обновился и проигрывается.",
    ),
    Step(
        "A", "Трек A: управление", "track_A_control.py",
        "Правый клик, прокрутка и двойной клик в режиме CONTROL.",
        "Запустите и нажмите 2 — режим CONTROL. ПКМ — щипок большим и "
        "средним. Прокрутка — два выпрямленных пальца и движение кисти "
        "вверх/вниз. Двойной клик — два быстрых щипка большим и указательным.",
        "1 CURSOR · 2 CONTROL · 3 VOLUME · 4 SLIDES · q — выход",
        "ПКМ открывает меню, страница едет, двойной клик открывает папку.",
        warning="Шаг управляет реальной мышью: ПКМ и клики настоящие.",
        extra=True,
    ),
    Step(
        "K", "Калибровка под руку", "calibrate_pinch.py",
        "Скрипт измеряет сомкнутый и разведённый щипок и рекомендует пороги.",
        "Запустите и держите руку в кадре. Первые 3 секунды — сомкнутый "
        "щипок, затем 3 секунды — разведённый. Результат появится в консоли "
        "и в файле calibration.txt.",
        "q — прервать",
        "Диапазоны не пересеклись, в calibration.txt есть строки для common.py.",
        extra=True,
    ),
    Step(
        "T", "Автотесты логики", "tests/test_logic.py",
        "Проверка жестов, кликов, прокрутки и гистерезиса без камеры.",
        "Запустите и дождитесь финального «Все проверки пройдены». Отчёт "
        "сохраняется в tests/test_report.txt. Камера и реальные клики не "
        "используются.",
        "Автоматически, без участия",
        "Все строки [OK], ошибок нет.",
        extra=True,
    ),
]


def read_thresholds():
    """Достаёт текущие пороги из common.py для нижней строки."""
    try:
        text = (ROOT / "common.py").read_text(encoding="utf-8")
        pinch = re.search(r"PINCH_ON,\s*PINCH_OFF\s*=\s*([0-9.]+),\s*([0-9.]+)", text)
        frames = re.search(r"GESTURE_FRAMES\s*=\s*(\d+)", text)
        if pinch and frames:
            return f"PINCH_ON {pinch.group(1)} · PINCH_OFF {pinch.group(2)} · GESTURE_FRAMES {frames.group(1)}"
    except OSError:
        pass
    return "Пороги: common.py"


def focus_window(title):
    """Поднимает окно OpenCV: иначе оно может остаться за другими окнами."""
    if sys.platform != "win32" or not title:
        return
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    for _ in range(50):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            return
        time.sleep(0.1)


def dependency_report():
    modules = ["cv2", "mediapipe", "pyautogui", "PIL"]
    if sys.platform == "win32":
        modules.append("pycaw")
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if not MODEL.exists():
        missing.append("models/hand_landmarker.task")
    return missing


class HintCard:
    """Небольшая карточка поверх окон: что делать и какие клавиши."""

    def __init__(self, root, on_stop):
        self.root = root
        self.on_stop = on_stop
        self.win = None

    def show(self, step: Step, allow_stop=True):
        self.hide()
        win = tk.Toplevel(self.root)
        self.win = win
        win.title("Инструкция — Гестурный пульт")
        win.configure(bg=PANEL)
        win.attributes("-topmost", True)
        win.resizable(False, False)

        accent = tk.Frame(win, bg=ACCENT, height=5)
        accent.pack(fill="x")

        body = tk.Frame(win, bg=PANEL, padx=18, pady=12)
        body.pack(fill="both", expand=True)

        kind = "ДОПОЛНИТЕЛЬНО" if step.extra else f"ШАГ {step.sid} ИЗ 10"
        tk.Label(body, text=kind, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(body, text=step.title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 15), justify="left",
                 wraplength=360).pack(anchor="w", pady=(2, 6))
        tk.Label(body, text=step.summary, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10), justify="left",
                 wraplength=360).pack(anchor="w")
        if step.warning:
            tk.Label(body, text="⚠ " + step.warning, bg=PANEL, fg=RED,
                     font=("Segoe UI", 9), justify="left",
                     wraplength=360).pack(anchor="w", pady=(7, 0))
        tk.Label(body, text="Клавиши: " + step.keys, bg=PANEL, fg=BLUE,
                 font=("Consolas", 9), justify="left",
                 wraplength=360).pack(anchor="w", pady=(9, 0))

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="Подробности — в окне пульта", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        if allow_stop and self.on_stop:
            tk.Button(row, text="Стоп", command=self.on_stop, bg="#4a2421",
                      fg="#ffd6d2", activebackground="#6b302b",
                      activeforeground=TEXT, relief="flat", bd=0,
                      font=("Segoe UI Semibold", 8), padx=10, pady=3,
                      cursor="hand2").pack(side="right", padx=(6, 0))
        tk.Button(row, text="Скрыть", command=self.hide, bg=PANEL2, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, relief="flat",
                  bd=0, font=("Segoe UI", 8), padx=10, pady=3,
                  cursor="hand2").pack(side="right")

        win.update_idletasks()
        width = 410
        height = win.winfo_reqheight()
        x = max(12, win.winfo_screenwidth() - width - 24)
        y = 24
        win.geometry(f"{width}x{height}+{x}+{y}")

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


class Hub:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Гестурный пульт — учебный агрегатор")
        self.root.configure(bg=BG)
        self.root.minsize(980, 660)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.completed: set[str] = set()
        self.last = "1"
        self.load_state()

        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue = queue.Queue()
        self.current: int | None = None
        self.running = False
        self.auto = False
        self.stopping = False
        self.alive = True
        self.card = HintCard(root, self.stop)
        self.status = tk.StringVar(value="Выберите шаг и нажмите «Запустить».")
        self.thresholds = tk.StringVar(value=read_thresholds())

        self.build()
        self.refresh_list()
        self.show_step(self.index_of(self.last))
        self.root.after(120, self.poll)

    # ---- состояние --------------------------------------------------------
    def load_state(self):
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
            ids = data.get("completed", [])
            if isinstance(ids, list):
                self.completed = {str(x) for x in ids}
            last = str(data.get("last", "1"))
            if last in {s.sid for s in STEPS}:
                self.last = last
        except (OSError, ValueError, TypeError):
            pass

    def save_state(self):
        try:
            STATE.write_text(json.dumps(
                {"completed": sorted(self.completed), "last": self.last},
                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    # ---- интерфейс --------------------------------------------------------
    def build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 8))

        tk.Label(header, text="ГЕСТУРНЫЙ ПУЛЬТ", bg=BG, fg=ACCENT,
                 font=("Segoe UI Semibold", 22)).pack(side="left")
        tk.Label(header, text="  лабораторная № 4 · трек A", bg=BG, fg=MUTED,
                 font=("Segoe UI", 11)).pack(side="left", pady=(9, 0))

        right_head = tk.Frame(header, bg=BG)
        right_head.pack(side="right")
        self.progress_var = tk.StringVar(value="")
        self.progress = tk.Label(right_head, textvariable=self.progress_var,
                                 bg=BG, fg=MUTED,
                                 font=("Segoe UI Semibold", 9))
        self.progress.pack(anchor="e")
        self.bar = tk.Canvas(right_head, width=220, height=6, bg=BORDER,
                             highlightthickness=0)
        self.bar.pack(anchor="e", pady=(4, 0))
        self.bar_fill = self.bar.create_rectangle(0, 0, 0, 6, fill=ACCENT,
                                                  width=0)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=(4, 8))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=PANEL, highlightbackground=BORDER,
                        highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        tk.Label(left, text="МАРШРУТ", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI Semibold", 8)).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.listbox = tk.Listbox(
            left, bg=PANEL, fg=TEXT, selectbackground=ACCENT,
            selectforeground=BG, activestyle="none", borderwidth=0,
            highlightthickness=0, exportselection=False,
            font=("Segoe UI", 10), height=13, width=38)
        self.listbox.grid(row=1, column=0, sticky="nsew", padx=8)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        self.listbox.bind("<Double-Button-1>", lambda e: self.run_selected())

        buttons = tk.Frame(left, bg=PANEL)
        buttons.grid(row=2, column=0, sticky="ew", padx=12, pady=(10, 12))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

        self.btn_run = self.button(buttons, "▶  Запустить", self.run_selected,
                                   accent=True)
        self.btn_run.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.btn_all = self.button(buttons, "▶▶  Пройти всё", self.run_all)
        self.btn_all.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.btn_hint = self.button(buttons, "Инструкция", self.show_hint)
        self.btn_hint.grid(row=2, column=0, sticky="ew", padx=(0, 3))
        self.btn_readme = self.button(buttons, "README", self.open_readme)
        self.btn_readme.grid(row=2, column=1, sticky="ew", padx=(3, 0))

        self.btn_stop = self.button(buttons, "■  Остановить", self.stop)
        self.btn_stop.grid(row=3, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.btn_reset = self.button(buttons, "Сброс", self.reset)
        self.btn_reset.grid(row=3, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(22, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self.details = tk.Text(
            right, bg=BG, fg=TEXT, bd=0, highlightthickness=0, wrap="word",
            font=("Segoe UI", 11), padx=0, pady=0, cursor="arrow",
            selectbackground=BORDER, selectforeground=TEXT, height=18)
        self.details.grid(row=0, column=0, sticky="nsew")
        self.details.tag_configure("eyebrow", foreground=ACCENT,
                                   font=("Segoe UI Semibold", 8),
                                   spacing3=4)
        self.details.tag_configure("h", foreground=TEXT,
                                   font=("Segoe UI Semibold", 20),
                                   spacing3=6)
        self.details.tag_configure("summary", foreground=MUTED,
                                   font=("Segoe UI", 10), spacing3=10)
        self.details.tag_configure("warn", foreground=RED,
                                   font=("Segoe UI", 10), spacing3=8)
        self.details.tag_configure("label", foreground=ACCENT,
                                   font=("Segoe UI Semibold", 8),
                                   spacing1=10, spacing3=3)
        self.details.tag_configure("body", foreground=TEXT,
                                   font=("Segoe UI", 11), spacing3=7)
        self.details.tag_configure("code", foreground=BLUE,
                                   font=("Consolas", 10), spacing3=7)

        log_head = tk.Frame(right, bg=BG)
        log_head.grid(row=2, column=0, sticky="ew", pady=(14, 4))
        tk.Label(log_head, text="ЖУРНАЛ", bg=BG, fg=ACCENT,
                 font=("Segoe UI Semibold", 8)).pack(side="left")
        tk.Label(log_head, text="  F5 — запустить · Esc — остановить",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")

        self.log = tk.Text(right, bg="#0c0a09", fg="#cfc6ba", bd=0,
                           highlightthickness=0, wrap="word", height=7,
                           font=("Consolas", 9), padx=10, pady=8,
                           state="disabled")
        self.log.grid(row=3, column=0, sticky="nsew")
        self.log.tag_configure("ok", foreground=GREEN)
        self.log.tag_configure("err", foreground=RED)
        self.log.tag_configure("accent", foreground=ACCENT)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        tk.Label(footer, textvariable=self.thresholds, bg=BG, fg=MUTED,
                 font=("Consolas", 8), anchor="e").pack(side="right")

        self.root.bind("<F5>", lambda e: self.run_selected())
        self.root.bind("<Escape>", lambda e: self.stop())

    def button(self, parent, text, command, accent=False):
        bg = ACCENT if accent else PANEL2
        fg = BG if accent else TEXT
        return tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg,
            activebackground="#ffd36a" if accent else BORDER,
            activeforeground=BG if accent else TEXT,
            disabledforeground="#766b60", relief="flat", bd=0,
            font=("Segoe UI Semibold", 9), padx=10, pady=7,
            cursor="hand2")

    def refresh_list(self):
        selected = self.selected()
        self.listbox.delete(0, "end")
        for i, step in enumerate(STEPS):
            mark = "✓" if step.sid in self.completed else "○"
            self.listbox.insert("end", f" {mark}  {step.sid:>2}  {step.title}")
            self.listbox.itemconfig(i, foreground=GREEN if mark == "✓" else TEXT)
        if selected is not None:
            self.listbox.selection_set(selected)
            self.listbox.see(selected)
        done = len([s for s in STEPS[:CORE] if s.sid in self.completed])
        self.progress_var.set(f"выполнено {done} из {CORE}")
        self.bar.coords(self.bar_fill, 0, 0, int(220 * done / CORE), 6)

    def show_step(self, index):
        if index is None:
            return
        index = max(0, min(index, len(STEPS) - 1))
        self.last = STEPS[index].sid
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.see(index)
        step = STEPS[index]
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        kind = "ДОПОЛНИТЕЛЬНО" if step.extra else f"ШАГ {step.sid} ИЗ 10"
        self.details.insert("end", kind + "\n", "eyebrow")
        self.details.insert("end", step.title + "\n", "h")
        self.details.insert("end", step.summary + "\n", "summary")
        if step.warning:
            self.details.insert("end", "⚠ " + step.warning + "\n", "warn")
        self.details.insert("end", "ЧТО ДЕЛАТЬ\n", "label")
        self.details.insert("end", step.do + "\n", "body")
        self.details.insert("end", "КЛАВИШИ\n", "label")
        self.details.insert("end", step.keys + "\n", "code")
        self.details.insert("end", "ПРОВЕРКА\n", "label")
        self.details.insert("end", step.check + "\n", "body")
        self.details.configure(state="disabled")
        self.save_state()

    def index_of(self, sid):
        for i, step in enumerate(STEPS):
            if step.sid == sid:
                return i
        return 0

    def selected(self):
        cur = self.listbox.curselection()
        return int(cur[0]) if cur else None

    def on_select(self, _event=None):
        index = self.selected()
        if index is not None and not self.running:
            self.show_step(index)

    def set_running(self, running):
        self.running = running
        state = "disabled" if running else "normal"
        self.listbox.configure(state=state)
        for btn in (self.btn_run, self.btn_all, self.btn_reset, self.btn_hint):
            btn.configure(state=state)
        self.btn_stop.configure(state="normal" if running else "disabled")

    # ---- запуск -----------------------------------------------------------
    def run_selected(self):
        if self.running:
            return
        index = self.selected()
        if index is None:
            index = 0
        self.auto = False
        self.run_step(index)

    def run_all(self):
        if self.running:
            return
        if not messagebox.askyesno(
                "Пройти всё",
                "Будут запущены шаги 1–10 подряд.\n\n"
                "Шаги 4, 5, 8 и 9 управляют реальной мышью, громкостью "
                "и клавишами. Продолжить?",
                parent=self.root):
            return
        start = self.selected()
        if start is None or start >= CORE:
            start = 0
        self.auto = True
        self.show_step(start)
        self.run_step(start)

    def run_step(self, index):
        if self.running:
            return
        step = STEPS[index]
        script = ROOT / step.script
        if not script.exists():
            messagebox.showerror("Нет файла", f"Не найден файл:\n{script}",
                                 parent=self.root)
            return
        self.current = index
        self.stopping = False
        self.set_running(True)
        self.show_step(index)
        self.card.show(step)
        self.append_log(f"\n───── {step.sid}. {step.title} ─────", "accent")
        self.status.set(f"Выполняется шаг {step.sid}: {step.title}…")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-u", str(script)],
                cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags)
        except OSError as exc:
            self.proc = None
            self.set_running(False)
            self.card.hide()
            self.status.set("Не удалось запустить шаг.")
            self.append_log(f"Ошибка запуска: {exc}", "err")
            return

        proc = self.proc
        threading.Thread(target=self.reader, args=(proc,),
                         daemon=True).start()
        threading.Thread(target=focus_window, args=(step.window,),
                         daemon=True).start()
        self.thresholds.set(read_thresholds())

    def reader(self, proc):
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    self.q.put(("line", line.rstrip("\r\n")))
        except Exception as exc:  # поток чтения не должен падать молча
            self.q.put(("line", f"[ошибка чтения вывода] {exc}"))
        code = proc.wait()
        self.q.put(("exit", code))

    def poll(self):
        if not self.alive:
            return
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                self.append_log(payload)
            elif kind == "exit":
                self.finished(payload)
        self.root.after(120, self.poll)

    def finished(self, code):
        step = STEPS[self.current] if self.current is not None else None
        self.proc = None
        self.set_running(False)
        self.card.hide()
        stopped = self.stopping
        self.stopping = False

        if stopped:
            self.auto = False
            self.status.set("Остановлено пользователем.")
            self.append_log("Остановлено.", "err")
            return

        if code == 0 and step is not None:
            self.completed.add(step.sid)
            self.save_state()
            self.refresh_list()
            self.append_log(f"Шаг {step.sid} завершён.", "ok")
            self.status.set(f"Шаг {step.sid} завершён.")
            if self.auto and self.current is not None and self.current < CORE - 1:
                self.status.set("Шаг завершён. Следующий через секунду…")
                self.root.after(900, self.auto_next)
            elif self.auto:
                self.auto = False
                self.status.set("Все шаги 1–10 пройдены.")
            return

        self.auto = False
        self.status.set(f"Шаг завершён с ошибкой (код {code}).")
        self.append_log(f"Процесс завершился с кодом {code}.", "err")

    def auto_next(self):
        if not self.auto or self.running:
            return
        if self.current is None or self.current >= CORE - 1:
            self.auto = False
            return
        self.show_step(self.current + 1)
        self.run_step(self.current + 1)

    def stop(self):
        if self.proc is None:
            return
        self.stopping = True
        self.auto = False
        self.status.set("Останавливаю шаг…")
        proc = self.proc
        try:
            proc.terminate()
        except OSError:
            pass
        self.root.after(2000, lambda: self.kill_if_alive(proc))

    def kill_if_alive(self, proc):
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    # ---- журнал и прочее --------------------------------------------------
    def append_log(self, line, tag=None):
        if not line:
            return
        noisy = ("INFO:", "W0000", "I0000", "WARNING: Logging before InitGoogle")
        if line.startswith(noisy):
            return
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", tag)
        if int(self.log.index("end-1c").split(".")[0]) > 400:
            self.log.delete("1.0", "80.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def show_hint(self):
        index = self.selected()
        if index is not None and not self.running:
            self.card.show(STEPS[index], allow_stop=False)

    def reset(self):
        if self.running:
            return
        if not self.completed:
            return
        if messagebox.askyesno("Сброс", "Снять отметки о выполнении всех шагов?",
                               parent=self.root):
            self.completed.clear()
            self.save_state()
            self.refresh_list()
            self.status.set("Прогресс сброшен.")

    def open_readme(self):
        path = ROOT / "README.md"
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606
            else:
                import webbrowser
                webbrowser.open(path.as_uri())
        except OSError as exc:
            messagebox.showerror("README", f"Не удалось открыть файл:\n{exc}",
                                 parent=self.root)

    def close(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
            except OSError:
                pass
        self.alive = False
        self.save_state()
        self.root.destroy()


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    hub = Hub(root)

    missing = dependency_report()
    if missing:
        hub.status.set("Не хватает: " + ", ".join(missing))
        hub.append_log("Не хватает: " + ", ".join(missing), "err")
    else:
        hub.status.set("Окружение готово. Выберите шаг и нажмите «Запустить».")
        hub.append_log("Модель и зависимости на месте.", "ok")

    root.update_idletasks()
    width, height = 1120, 760
    x = max(20, (root.winfo_screenwidth() - width) // 2)
    y = max(20, (root.winfo_screenheight() - height) // 2 - 20)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.mainloop()


if __name__ == "__main__":
    main()
