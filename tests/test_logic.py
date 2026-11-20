"""Автопроверка логики без камеры и без реальных кликов.

Запуск:  python tests/test_logic.py
Скрипт подменяет pyautogui заглушкой и прогоняет жесты на синтетической
кисти из hand_model.py. Результаты печатаются и сохраняются в
tests/test_report.txt.
"""

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import common
import hand_model as hm
import track_A_control as track


class FakeGui:
    def __init__(self):
        self.calls = []

    def size(self):
        return (1920, 1080)

    def moveTo(self, x, y):
        self.calls.append(("move", x, y))

    def mouseDown(self, button="left"):
        self.calls.append(("down", button))

    def mouseUp(self, button="left"):
        self.calls.append(("up", button))

    def click(self, x=None, y=None, button="left", clicks=1):
        self.calls.append(("click", button))

    def doubleClick(self, x=None, y=None, button="left"):
        self.calls.append(("double", button))

    def scroll(self, units):
        self.calls.append(("scroll", units))

    def press(self, key):
        self.calls.append(("press", key))

    def count(self, kind):
        return sum(1 for c in self.calls if c[0] == kind)

    def clear(self):
        self.calls.clear()


fake = FakeGui()
common.pyautogui = fake
track.pyautogui = fake

PALM = hm.place(hm.pose("palm"), (0.5, 0.8))
FIST = hm.place(hm.pose("fist"), (0.5, 0.8))
GUN = hm.place(hm.pose("gun"), (0.5, 0.8))
TWO = hm.place(hm.pose("two"), (0.5, 0.8))
CLOSED = hm.place(hm.pose("pinch_closed"), (0.5, 0.8))
HALF = hm.place(hm.pose("pinch_half"), (0.5, 0.8))
OPEN = hm.place(hm.pose("pinch_open"), (0.5, 0.8))
RIGHT = hm.place(hm.pose("right_pinch"), (0.5, 0.8))

OUT = []


def log(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    OUT.append(line)


def check(name, condition, detail=""):
    status = "OK  " if condition else "FAIL"
    log(f"[{status}] {name} {detail}")
    if not condition:
        raise AssertionError(name)


def feed(ctrl, pts, t):
    ctrl.update(pts, now=t)


def test_geometry():
    log("\n== Геометрия и жесты ==")
    palm, fist = hm.pose("palm"), hm.pose("fist")
    closed, half = hm.pose("pinch_closed"), hm.pose("pinch_half")
    open_p = hm.pose("pinch_open")
    log(f"pinch_strength: open={common.pinch_strength(open_p):.3f} "
        f"half={common.pinch_strength(half):.3f} closed={common.pinch_strength(closed):.3f}")
    check("открытый щипок больше закрытого",
          common.pinch_strength(open_p) > common.pinch_strength(half)
          > common.pinch_strength(closed))
    check("закрытый щипок ниже PINCH_ON", common.pinch_strength(closed) < common.PINCH_ON)
    check("открытый щипок выше PINCH_OFF", common.pinch_strength(open_p) > common.PINCH_OFF)
    check("ладонь распознаётся", common.gesture(palm) == "PALM")
    check("кулак распознаётся", common.gesture(fist) == "FIST")
    check("пистолет распознаётся", common.gesture(hm.pose("gun")) == "GUN")
    check("два пальца не PALM/GUN", common.gesture(hm.pose("two")) is None)
    check("два пальца включают прокрутку", track.is_scroll_pose(hm.pose("two")))
    check("щипок не включает прокрутку", not track.is_scroll_pose(closed))
    check("кулак по углам", track.is_fist(fist))


def test_debounce():
    log("\n== Дребезг: один порог vs гистерезис ==")
    rnd = random.Random(7)
    db = track.Debouncer(common.PINCH_ON, common.PINCH_OFF, frames=2)
    raw_state = deb_state = False
    raw_flips = deb_flips = 0
    values = []
    # Медленно ведём щипок через порог и обратно с шумом 3% размера кисти.
    for i in range(600):
        u = i / 599
        base = 0.25 + 0.45 * math.sin(u * 2 * math.pi)
        values.append(base + rnd.gauss(0, 0.03))
    for v in values:
        raw = v < common.PINCH_ON
        deb = db.update(v)
        raw_flips += raw != raw_state
        deb_flips += deb != deb_state
        raw_state, deb_state = raw, deb
    log(f"600 кадров: raw_flips={raw_flips} deb_flips={deb_flips}")
    check("гистерезис уменьшает число переключений", deb_flips < raw_flips,
          f"({deb_flips} < {raw_flips})")


def test_hold():
    log("\n== GESTURE_FRAMES: 1 / 4 / 50 ==")
    stream = (["FIST"] * 10 + ["GUN"] * 3 + ["PALM"] * 30 + [None] * 3
              + ["GUN"] * 30 + ["PALM"] * 6)
    for need in (1, 4, 50):
        h = common.Hold(need)
        fired = [h.update(g) for g in stream]
        names = [g for g in fired if g]
        log(f"need={need:<3} срабатываний={len(names)} {names}")
        if need == 1:
            check("при 1 переходный GUN тоже срабатывает", names.count("GUN") >= 2)
        if need == 4:
            check("при 4 срабатывают только устойчивые жесты", len(names) == 4, names)
        if need == 50:
            check("при 50 короткие жесты не успевают", len(names) == 0)


def test_cursor():
    log("\n== Курсор и левая кнопка ==")
    fake.clear()
    cur = common.Cursor()
    for _ in range(4):
        cur.update(CLOSED)
    for _ in range(4):
        cur.update(PALM)
    log("вызовы:", fake.calls)
    check("нажатие и отпускание ЛКМ", fake.count("down") == 1 and fake.count("up") == 1)
    check("курсор двигался", fake.count("move") > 0)


def test_control_mouse():
    log("\n== Трек A: правый клик ==")
    fake.clear()
    ctrl = track.ControlMouse()
    t = 1.0
    for _ in range(6):
        feed(ctrl, RIGHT, t)
        t += 1 / 30
    for _ in range(10):
        feed(ctrl, PALM, t)
        t += 1 / 30
    log("вызовы:", fake.calls)
    check("правый клик ровно один", fake.count("click") == 1
          and ("click", "right") in fake.calls)
    ctrl.release()

    log("\n== Трек A: одиночный клик ==")
    fake.clear()
    ctrl = track.ControlMouse()
    t = 1.0
    for _ in range(3):
        feed(ctrl, CLOSED, t)
        t += 1 / 30
    for _ in range(20):
        feed(ctrl, PALM, t)
        t += 1 / 30
    log("вызовы:", fake.calls)
    check("одиночный клик один", fake.count("click") == 1 and fake.count("double") == 0)
    ctrl.release()

    log("\n== Трек A: двойной клик ==")
    fake.clear()
    ctrl = track.ControlMouse()
    t = 1.0
    for _ in range(3):
        feed(ctrl, CLOSED, t)
        t += 1 / 30
    for _ in range(6):
        feed(ctrl, PALM, t)
        t += 1 / 30
    for _ in range(3):
        feed(ctrl, CLOSED, t)
        t += 1 / 30
    for _ in range(20):
        feed(ctrl, PALM, t)
        t += 1 / 30
    log("вызовы:", fake.calls)
    check("двойной клик и нет лишнего одиночного",
          fake.count("double") == 1 and fake.count("click") == 0)
    ctrl.release()

    log("\n== Трек A: перетаскивание ==")
    fake.clear()
    ctrl = track.ControlMouse()
    t = 1.0
    for _ in range(15):
        feed(ctrl, CLOSED, t)
        t += 1 / 30
    for _ in range(6):
        feed(ctrl, PALM, t)
        t += 1 / 30
    log("вызовы:", fake.calls)
    check("есть mouseDown и mouseUp, нет click",
          fake.count("down") == 1 and fake.count("up") == 1 and fake.count("click") == 0)
    ctrl.release()

    log("\n== Трек A: прокрутка ==")
    fake.clear()
    ctrl = track.ControlMouse()
    t = 1.0
    base = hm.place(hm.pose("two"), (0.55, 0.80))
    for _ in range(8):                      # поза устаканивается
        feed(ctrl, base, t)
        t += 1 / 30
    for i in range(1, 16):                  # ведём кисть вверх
        feed(ctrl, hm.place(hm.pose("two"), (0.55, 0.80 - i * 0.008)), t)
        t += 1 / 30
    scrolls = [c for c in fake.calls if c[0] == "scroll"]
    log("вызовы колеса:", scrolls)
    check("колесо крутится вверх", scrolls and all(u > 0 for _, u in scrolls))
    check("между щелчками есть пауза", len(scrolls) <= 8, f"({len(scrolls)} <= 8)")
    check("прокрутка не двигает курсор", fake.count("move") == 0)
    ctrl.release()


def test_volume_curve():
    log("\n== Громкость ==")
    for level in (0.0, 0.5, 1.0):
        pts = hm.pinch_pose(level)
        log(f"щипок {level:.1f}: pinch={common.pinch_strength(pts):.2f} "
            f"-> vol={common.pinch_level(pts):.0%}")


def main():
    test_geometry()
    test_debounce()
    test_hold()
    test_cursor()
    test_control_mouse()
    test_volume_curve()
    log("\nВсе проверки пройдены.")
    (ROOT / "tests" / "test_report.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
