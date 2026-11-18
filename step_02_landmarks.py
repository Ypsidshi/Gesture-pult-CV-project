"""Шаг 2. Скелет кисти из 21 точки. Выход — q."""

from common import *

cap, tr = open_camera(), Tracker()
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    if pts:
        draw(frame, pts)
    if show("step_02", frame) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
