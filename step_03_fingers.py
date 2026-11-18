"""Шаг 3. Счёт выпрямленных пальцев. Выход — q."""

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
        cv2.putText(frame, str(sum(fingers_up(pts))), (280, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 8)
    if show("step_03", frame) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
