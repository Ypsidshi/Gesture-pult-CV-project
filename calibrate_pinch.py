"""Калибровка щипка под свою руку.

Программа просит 3 секунды держать сомкнутый щипок, затем 3 секунды
разведённый и по замерам рекомендует PINCH_ON, PINCH_OFF, VOL_MIN, VOL_MAX
для common.py.

Запуск:  python calibrate_pinch.py
Выход:   q
"""

import time
from pathlib import Path
from statistics import median

import cv2
import numpy as np

from common import Tracker, open_camera, pinch_strength

SECONDS = 3.0


def percentile(values, q):
    return float(np.percentile(values, q)) if values else float("nan")


def collect(cap, tr, title, prompt, seconds=SECONDS):
    values = []
    t0 = time.monotonic()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        pts = tr(frame)
        left = max(0.0, seconds - (time.monotonic() - t0))
        if pts:
            values.append(pinch_strength(pts))
            cv2.putText(frame, f"{pinch_strength(pts):.2f}", (250, 330),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 5)
        cv2.rectangle(frame, (40, 400), (600, 430), (60, 60, 60), -1)
        cv2.rectangle(frame, (40, 400),
                      (40 + int(560 * (1 - left / seconds)), 430), (0, 200, 255), -1)
        cv2.putText(frame, prompt, (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (255, 255, 255), 2)
        cv2.putText(frame, f"{left:.1f}", (40, 380), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (200, 200, 200), 2)
        cv2.imshow(title, frame)
        if cv2.waitKey(1) & 0xFF == ord('q') or left <= 0:
            break
    return values


def main():
    cap, tr = open_camera(), Tracker()
    print("Держите руку в кадре. Для выхода нажмите q в окне.")

    closed = collect(cap, tr, "calibration",
                     "1/2: CLOSED pinch (thumb + index together)")
    time.sleep(0.4)
    opened = collect(cap, tr, "calibration",
                     "2/2: OPEN pinch (thumb and index apart)")

    cv2.destroyAllWindows()
    cap.release()

    if len(closed) < 10 or len(opened) < 10:
        raise SystemExit("Мало данных: рука плохо видна в кадре.")

    c_lo, c_hi = percentile(closed, 5), percentile(closed, 95)
    o_lo, o_hi = percentile(opened, 5), percentile(opened, 95)

    if o_lo <= c_hi:
        raise SystemExit("Диапазоны пересеклись: повторите калибровку.")

    gap = o_lo - c_hi
    pinch_on = round(c_hi + 0.25 * gap, 2)
    pinch_off = round(c_hi + 0.45 * gap, 2)
    vol_min = round(c_hi + 0.05 * gap, 2)
    vol_max = round(o_lo - 0.03 * gap, 2)

    lines = [
        "Калибровка щипка",
        f"сомкнутый: медиана {median(closed):.3f}, p05 {c_lo:.3f}, p95 {c_hi:.3f}, "
        f"кадров {len(closed)}",
        f"разведённый: медиана {median(opened):.3f}, p05 {o_lo:.3f}, p95 {o_hi:.3f}, "
        f"кадров {len(opened)}",
        "",
        "Вставьте в common.py:",
        f"PINCH_ON, PINCH_OFF = {pinch_on}, {pinch_off}",
        f"VOL_MIN, VOL_MAX, VOL_STEP = {vol_min}, {vol_max}, 0.02",
    ]
    text = "\n".join(lines)
    print(text)
    (Path(__file__).resolve().parent / "calibration.txt").write_text(
        text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
