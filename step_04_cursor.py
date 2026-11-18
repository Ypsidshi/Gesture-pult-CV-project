"""Шаг 4. Курсор за рукой и клик щипком. Выход — q."""

from common import *

cap, tr, cur = open_camera(), Tracker(), Cursor()
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    if pts:
        draw(frame, pts)
        cur.update(pts)
        pinch = pinch_strength(pts)
        cv2.putText(frame, f"pinch {pinch:.2f}  LMB {int(cur.down)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    else:
        cur.release()
    if show("step_04", frame) == ord('q'):
        break

cur.release()
cap.release()
cv2.destroyAllWindows()
