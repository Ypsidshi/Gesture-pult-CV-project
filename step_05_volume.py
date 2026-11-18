"""Шаг 5. Режимы IDLE / VOLUME / CURSOR по числу пальцев. Выход — q."""

from collections import deque
from statistics import median

from common import *

cap, tr, cur = open_camera(), Tracker(), Cursor()
hist = deque(maxlen=5)
mode, vol = "IDLE", 0.0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    if pts:
        draw(frame, pts)
        hist.append(sum(fingers_up(pts)[1:]))
        n = median(hist)
        mode = "IDLE" if n < 0.5 else "VOLUME" if n < 1.5 else "CURSOR" if n > 3.5 else mode
        if mode == "CURSOR":
            cur.update(pts)
        else:
            cur.release()
        if mode == "VOLUME":
            level = pinch_level(pts)
            if abs(level - vol) >= VOL_STEP:
                set_volume(level)
                vol = level
    else:
        hist.clear()
        cur.release()

    cv2.putText(frame, f"{mode} vol {vol:.0%}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    if show("step_05", frame) == ord('q'):
        break

cur.release()
cap.release()
cv2.destroyAllWindows()
