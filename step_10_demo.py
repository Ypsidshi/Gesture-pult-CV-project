"""Шаг 10. Тот же итоговый пульт, но с записью demo.gif.

Нажмите r перед показом сценария и r после. Если нажать q во время записи,
ролик тоже сохранится. Файл demo.gif появится рядом со скриптом.
"""

from common import *

MODES = ["CURSOR", "VOLUME", "SLIDES"]
COLOR = {"CURSOR": (0, 255, 0), "VOLUME": (0, 255, 255), "SLIDES": (255, 200, 0)}
KEY = {"PALM": "right", "GUN": "left"}
FIST_HOLD = 40          # ~1,3 с при 30 FPS: короткий кулак режим не переключает

cap, tr, cur, hold = open_camera(), Tracker(), Cursor(), Hold()
mode_i, fist_n, vol = 0, 0, 0.0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    pts = tr(frame)

    if pts:
        draw(frame, pts)
        g = gesture(pts)
        if g == "FIST":
            fist_n += 1
        else:
            if fist_n >= FIST_HOLD:
                mode_i = (mode_i + 1) % len(MODES)
                cur.release()
                hold.reset()
            fist_n = 0

        mode = MODES[mode_i]
        if mode == "CURSOR":
            cur.update(pts)
        elif mode == "VOLUME" and g != "FIST":
            level = pinch_level(pts)
            if abs(level - vol) >= VOL_STEP:
                set_volume(level)
                vol = level
        elif mode == "SLIDES":
            k = hold.update(g)
            if k in KEY:
                pyautogui.press(KEY[k])
    else:
        cur.release()
        hold.reset()
        fist_n = 0

    mode = MODES[mode_i]
    cv2.rectangle(frame, (0, 0), (639, 479), COLOR[mode], 6)
    cv2.putText(frame, f"{mode} click {int(cur.down)} vol {vol:.0%}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if rec.on:
        cv2.putText(frame, "REC", (560, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 255), 2)
    if fist_n:
        cv2.putText(frame, f"FIST {fist_n}/{FIST_HOLD}", (500, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    key = show("step_10", frame)
    if key == ord('q'):
        break
    if key in (ord('1'), ord('2'), ord('3')):
        mode_i = key - ord('1')
        cur.release()
        hold.reset()
        fist_n = 0

cur.release()
cap.release()
cv2.destroyAllWindows()
