"""Шаг 8. Жесты нажимают клавиши презентации.

PALM — right (вперёд), GUN — left (назад), FIST — space (пауза).
Одно нажатие за удержание. Выход — q.
"""

from common import *

ACTION = {"FIST": "space", "PALM": "right", "GUN": "left"}
cap, tr, hold = open_camera(), Tracker(), Hold()
label = ""

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)
    if pts:
        draw(frame, pts)
    g = hold.update(gesture(pts) if pts else None)
    if g:
        pyautogui.press(ACTION[g])
        label = ACTION[g]
    cv2.putText(frame, label, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                (0, 255, 255), 3)
    if show("step_08", frame) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
