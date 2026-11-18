"""Шаг 1. Проверка камеры: зеркальный кадр и FPS. Выход — q."""

import sys
import time

import cv2

# На Windows DirectShow открывает камеру быстрее и стабильнее, чем MSMF.
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

prev = time.monotonic()
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    now = time.monotonic()
    cv2.putText(frame, f"FPS {1 / max(now - prev, 1e-6):.0f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    prev = now
    cv2.imshow("step_01", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
