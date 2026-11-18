"""Трек A. Управление: правый клик, прокрутка и двойной клик.

Скрипт расширяет итоговый пульт (step_09_final.py) новым режимом CONTROL.
Режимы переключаются кулаком (удержание FIST_HOLD кадров) или клавишами 1-4.

CURSOR   — курсор и левая кнопка (перетаскивание), как в шаге 9;
CONTROL  — новые действия мыши:
             * щипок большой+средний (точки 4 и 12) — правый клик;
             * два пальца (указательный и средний) и движение кисти
               вверх/вниз — прокрутка колесом с паузой между щелчками;
             * два быстрых щипка большой+указательный — двойной клик;
VOLUME   — громкость щипком;
SLIDES   — ладонь/«пистолет» листают слайды.

Клавиша r включает запись demo.gif, q — выход.
"""

import time

from common import *

MODES = ["CURSOR", "CONTROL", "VOLUME", "SLIDES"]
COLOR = {"CURSOR": (0, 255, 0), "CONTROL": (0, 170, 255),
         "VOLUME": (0, 255, 255), "SLIDES": (255, 200, 0)}
KEY = {"PALM": "right", "GUN": "left"}
FIST_HOLD = 40          # ~1,3 с при 30 FPS: короткий кулак режим не переключает

# ---- Пороги трека A ------------------------------------------------------
RIGHT_ON, RIGHT_OFF = 0.50, 0.65   # щипок большой+средний
DOUBLE_MS = 0.45                   # окно двойного клика, с
CLICK_DELAY = DOUBLE_MS            # одиночный клик ждёт второй щипок
DRAG_DELAY = 0.30                  # после этого щипок становится перетаскиванием
SCROLL_SETTLE = 0.18               # пауза после входа в позу «два пальца»
SCROLL_STEP = 0.015                # сколько кисть должна пройти для щелчка колеса
SCROLL_UNITS = 3                   # строк на один щелчок
SCROLL_PAUSE = 0.10                # пауза между щелчками колеса


class Debouncer:
    """Гистерезис + подтверждение состояния несколько кадров подряд."""

    def __init__(self, on, off, frames=2):
        self.on, self.off, self.need = on, off, frames
        self.state, self.run = False, 0

    def update(self, value):
        raw = value < (self.off if self.state else self.on)
        self.run = 0 if raw == self.state else self.run + 1
        if self.run >= self.need:
            self.state, self.run = raw, 0
        return self.state


def pinch_mid(pts):
    """Щипок большого и среднего пальцев в размерах кисти."""
    return dist(pts[4], pts[12]) / max(dist(pts[0], pts[9]), 1e-6)


def is_fist(pts):
    """Кулак по углам: надёжнее расстояний, когда кисть повёрнута."""
    return not any(finger_states(pts, 150.0))


def is_scroll_pose(pts):
    """«Два пальца»: указательный и средний прямые, остальные согнуты.

    Дополнительно требуем, чтобы большой палец не был прижат к пальцам,
    иначе щипок ошибочно включал бы прокрутку.
    """
    s = finger_states(pts, 165.0)
    return (s[0] and s[1] and not s[2] and not s[3]
            and pinch_strength(pts) > 0.8 and pinch_mid(pts) > 0.8)


class ControlMouse:
    """Курсор + правый клик + прокрутка + одиночный/двойной клик."""

    def __init__(self):
        self.size = pyautogui.size()
        self.ema = self.last = None
        self.pinch = Debouncer(PINCH_ON, PINCH_OFF, frames=2)
        self.right = Debouncer(RIGHT_ON, RIGHT_OFF, frames=2)
        self.pinch_prev = self.right_prev = False

        self.pressed = False       # щипок ещё не превратился в клик/перетаскивание
        self.press_t = 0.0
        self.dragging = False
        self.pending_click = 0.0   # время отложенного одиночного клика
        self.right_t = 0.0
        self.left_block_until = 0.0  # пауза после правого клика

        self.scroll_ref = None
        self.scroll_acc = 0.0
        self.scroll_t = 0.0
        self.last_scroll_t = 0.0

        self.status, self.status_t = "READY", 0.0

    # ---- вспомогательное -------------------------------------------------
    def say(self, text, now=None):
        self.status = text
        self.status_t = now if now is not None else time.monotonic()

    def _move(self, pts):
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

    #
    def _left(self, pts, now, blocked):
        """Одиночный клик, перетаскивание и двойной клик."""
        # Отложенный одиночный клик: ждём, не начнётся ли второй щипок.
        if self.pending_click and now >= self.pending_click:
            pyautogui.click()
            self.pending_click = 0.0
            self.say("LMB", now)

        # Большой палец ближе к среднему — это правый щипок, не левый.
        mid = pinch_mid(pts)
        aim_right = mid < 0.55 or mid < pinch_strength(pts) * 1.2
        if aim_right:
            self.pending_click = 0.0

        state = self.pinch.update(pinch_strength(pts))
        if blocked or aim_right or now < self.left_block_until:
            state = False

        if state and not self.pinch_prev:
            if self.pending_click:
                # Второй щипок внутри окна: отменяем одиночный клик.
                self.pending_click = 0.0
                pyautogui.doubleClick()
                self.pressed = self.dragging = False
                self.say("DOUBLE", now)
            else:
                self.pressed = True
                self.press_t = now
                self.dragging = False

        if state and self.pressed and not self.dragging and now - self.press_t >= DRAG_DELAY:
            pyautogui.mouseDown()
            self.dragging = True
            self.say("DRAG", now)

        if not state and self.pinch_prev:
            if self.dragging:
                pyautogui.mouseUp()
                self.dragging = False
                self.say("DROP", now)
            elif self.pressed:
                # Короткий щипок: клик откладываем, чтобы поймать двойной.
                self.pending_click = now + CLICK_DELAY
            self.pressed = False

        self.pinch_prev = state
        return state

    def _right(self, pts, now, blocked):
        if blocked:
            self.right.state, self.right.run = False, 0
            self.right_prev = False
            return False
        state = self.right.update(pinch_mid(pts))
        if state and not self.right_prev and now - self.right_t > 0.35:
            pyautogui.click(button="right")
            self.right_t = now
            self.left_block_until = now + 1.2
            self.pending_click = 0.0
            self.say("RMB", now)
        self.right_prev = state
        return state

    def _scroll(self, pts, now, active):
        if not active:
            self.scroll_ref = None
            self.scroll_acc = 0.0
            return
        if self.scroll_ref is None:
            self.scroll_ref, self.scroll_t = pts[9].y, now
            return
        if now - self.scroll_t < SCROLL_SETTLE:
            self.scroll_ref = pts[9].y          # поза должна устояться
            return

        self.scroll_acc += self.scroll_ref - pts[9].y  # вверх по кадру = плюс
        if abs(self.scroll_acc) >= SCROLL_STEP and now - self.last_scroll_t >= SCROLL_PAUSE:
            steps = int(self.scroll_acc / SCROLL_STEP)
            units = max(-8, min(8, steps * SCROLL_UNITS))
            if units:
                pyautogui.scroll(units)
                self.say("SCROLL ^" if units > 0 else "SCROLL v", now)
                self.last_scroll_t = now
            self.scroll_acc -= steps * SCROLL_STEP

    def update(self, pts, now=None):
        now = now if now is not None else time.monotonic()
        fist = is_fist(pts)
        scroll = is_scroll_pose(pts) and not fist

        if not fist and not scroll:
            self._move(pts)

        right = self._right(pts, now, fist or scroll)
        # Пока активен правый щипок, левый не обрабатываем: жесты не конфликтуют.
        self._left(pts, now, fist or scroll or right or self.right_prev)
        self._scroll(pts, now, scroll)
        return fist, scroll

    def release(self):
        if self.dragging:
            pyautogui.mouseUp()
        self.dragging = self.pressed = False
        self.pending_click = 0.0
        self.ema = self.last = None
        self.scroll_ref = None
        self.scroll_acc = 0.0


def draw_ui(frame, mode, ctrl, fist_n, vol, scroll):
    color = COLOR[mode]
    cv2.rectangle(frame, (0, 0), (639, 479), color, 6)
    cv2.putText(frame, f"{mode}", (12, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    status = ctrl.status if time.monotonic() - ctrl.status_t < 1.0 else ""
    cv2.putText(frame, f"{status}  vol {vol:.0%}", (12, 68),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    if scroll:
        cv2.putText(frame, "SCROLL MODE", (440, 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 170, 255), 2)
    if fist_n:
        cv2.putText(frame, f"FIST {fist_n}/{FIST_HOLD}", (500, 68),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
    cv2.putText(frame, "1-4 mode  r rec  q quit", (12, 464),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)


def main():
    cap, tr, cur, hold, ctrl = (open_camera(), Tracker(), Cursor(), Hold(),
                                ControlMouse())
    mode_i, fist_n, vol = 0, 0, 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        pts = tr(frame)
        scroll = False

        if pts:
            draw(frame, pts)
            g = gesture(pts)
            if g == "FIST":
                fist_n += 1
            else:
                if fist_n >= FIST_HOLD:
                    mode_i = (mode_i + 1) % len(MODES)
                    cur.release()
                    ctrl.release()
                    hold.reset()
                fist_n = 0

            mode = MODES[mode_i]
            if mode == "CURSOR":
                cur.update(pts)
            elif mode == "CONTROL":
                _, scroll = ctrl.update(pts)
            elif mode == "VOLUME" and g != "FIST":
                level = pinch_level(pts)
                if abs(level - vol) >= VOL_STEP:
                    set_volume(level)
                    vol = level
            elif mode == "SLIDES":
                k = hold.update(g)
                if k in KEY:
                    pyautogui.press(KEY[k])
        else:
            cur.release()
            ctrl.release()
            hold.reset()
            fist_n = 0

        mode = MODES[mode_i]
        draw_ui(frame, mode, ctrl, fist_n, vol, scroll)

        key = show("track_A", frame)
        if key == ord('q'):
            break
        if key in (ord('1'), ord('2'), ord('3'), ord('4')):
            mode_i = key - ord('1')
            cur.release()
            ctrl.release()
            hold.reset()
            fist_n = 0

    cur.release()
    ctrl.release()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
