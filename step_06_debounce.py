"""Шаг 6. Сравнение наивного порога, гистерезиса и антидребезга.

На экране два счётчика: raw_flips (один порог) и deb_flips (два порога +
подтверждение 3 кадра). Выход — q.
"""

from collections import deque
from statistics import median

from common import *


class Debouncer:
    """Гистерезис + антидребезг: состояние меняется после need кадров."""

    def __init__(self, on, off, frames=3):
        self.on, self.off, self.need = on, off, frames
        self.state, self.run = False, 0

    def update(self, value):
        raw = value < (self.off if self.state else self.on)
        self.run = 0 if raw == self.state else self.run + 1
        if self.run >= self.need:
            self.state, self.run = raw, 0
        return self.state


cap, tr = open_camera(), Tracker()
db = Debouncer(PINCH_ON, PINCH_OFF)
hist = deque(maxlen=5)
raw_state, raw_flips, deb_state, deb_flips = False, 0, False, 0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    if pts:
        draw(frame, pts)
        pinch = pinch_strength(pts)
        raw, deb = pinch < PINCH_ON, db.update(pinch)
        raw_flips += raw != raw_state
        deb_flips += deb != deb_state
        raw_state, deb_state = raw, deb
        n = sum(fingers_up(pts))
        hist.append(n)
        cv2.putText(frame, f"raw {n}  stab {median(hist):.0f}  pinch {pinch:.2f}",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    cv2.putText(frame, f"raw_flips {raw_flips}  deb_flips {deb_flips}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    if show("step_06", frame) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
