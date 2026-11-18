"""Шаг 7. Жесты по углам в суставе PIP: FIST / PALM / GUN.

Жест засчитывается, только если удержан GESTURE_FRAMES кадров.
Выход — q.
"""

from common import *

COLOR = {"FIST": (0, 0, 255), "PALM": (0, 255, 0), "GUN": (255, 200, 0)}
cap, tr, hold = open_camera(), Tracker(), Hold()
fired, t_fired = "", 0.0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    g = gesture(pts) if pts else None
    if pts:
        draw(frame, pts)
    if g:
        cv2.rectangle(frame, (0, 0), (639, 479), COLOR[g], 6)
        cv2.putText(frame, g, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR[g], 3)

    if hold.update(g):
        fired, t_fired = g, time.monotonic()
    if time.monotonic() - t_fired < 0.7:
        cv2.putText(frame, f"FIRED {fired}", (10, 460), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (255, 255, 255), 3)
    if show("step_07", frame) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
