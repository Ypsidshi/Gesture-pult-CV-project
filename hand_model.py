"""Синтетическая модель кисти для демо-ролика и автотестов.

Модель не заменяет MediaPipe: она нужна, чтобы отрисовать demo.gif без
камеры, а также чтобы прогнать логику шагов на воспроизводимых позах.
Координаты точек те же, что у Hand Landmarker: 0 — запястье, 4 — кончик
большого пальца, 8 — указательного и т.д. Значения нормированы в 0..1.
"""

import math
import random


class P:
    """Точка с полями x, y — как NormalizedLandmark у MediaPipe."""

    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)

    def __repr__(self):
        return f"P({self.x:.3f}, {self.y:.3f})"


def _v(deg):
    """Единичный вектор: 0° — вверх, плюс — вправо."""
    r = math.radians(deg)
    return math.sin(r), -math.cos(r)


def _finger(mcp, lengths, curl, fan, sign):
    pts = []
    angle = fan
    p = mcp
    for i, length in enumerate(lengths):
        if i:
            angle += curl * (80 if i == 1 else 75) * sign
        dx, dy = _v(angle)
        p = (p[0] + dx * length, p[1] + dy * length)
        pts.append(p)
    return pts


# MCP четырёх пальцев: указательный, средний, безымянный, мизинец.
_MCP = {0: (-0.048, -0.135), 1: (-0.006, -0.145),
        2: (0.035, -0.137), 3: (0.066, -0.118)}
_LEN = {0: (0.060, 0.047, 0.036),
        1: (0.066, 0.052, 0.039),
        2: (0.060, 0.047, 0.036),
        3: (0.048, 0.038, 0.030)}
_FAN = {0: -6.0, 1: -1.0, 2: 5.0, 3: 12.0}
_SIGN = {0: 1.0, 1: 1.0, 2: -0.8, 3: -1.2}

_THUMB_BASE = (-0.070, -0.020)
_THUMB_OUT = [(-0.108, -0.052), (-0.140, -0.085), (-0.165, -0.115)]
_THUMB_FIST = [(-0.108, -0.052), (-0.062, -0.070), (-0.018, -0.100)]


def make_pose(curl=(0, 0, 0, 0), thumb="out", thumb_target=None):
    """Собирает 21 точку. curl — сгиб четырёх пальцев 0..1.

    thumb: "out", "fist" или "target"; при "target" кончик большого
    пальца ставится в thumb_target.
    """
    pts = [None] * 21
    pts[0] = (0.0, 0.0)
    for i, base in enumerate((5, 9, 13, 17)):
        mcp = _MCP[i]
        pts[base] = mcp
        chain = _finger(mcp, _LEN[i], curl[i], _FAN[i], _SIGN[i])
        pts[base + 1], pts[base + 2], pts[base + 3] = chain

    if thumb == "fist":
        thumb_pts = _THUMB_FIST
    else:
        thumb_pts = _THUMB_OUT
    if thumb == "target" and thumb_target is not None:
        mcp = (-0.108, -0.052)
        k = 0.68
        ip = (mcp[0] + (thumb_target[0] - mcp[0]) * k,
              mcp[1] + (thumb_target[1] - mcp[1]) * k)
        thumb_pts = [mcp, ip, thumb_target]

    pts[1] = _THUMB_BASE
    pts[2], pts[3], pts[4] = thumb_pts
    return [P(*p) for p in pts]


_CACHE = {}


def pose(name):
    """Именованная поза (кэшируется)."""
    if name in _CACHE:
        return _CACHE[name]
    if name == "palm":
        result = make_pose((0, 0, 0, 0), "out")
    elif name == "fist":
        result = make_pose((1, 1, 1, 1), "fist")
    elif name == "gun":
        result = make_pose((0, 1, 1, 1), "out")
    elif name == "two":
        result = make_pose((0, 0, 1, 1), "out")
    elif name == "pinch_closed":
        base = make_pose((0.12, 0.82, 0.9, 0.95), "out")
        target = (base[8].x + 0.008, base[8].y + 0.010)
        result = make_pose((0.12, 0.82, 0.9, 0.95), "target", target)
    elif name == "pinch_open":
        result = make_pose((0, 0, 0, 0), "out")
    elif name == "pinch_half":
        base = make_pose((0.06, 0.3, 0.5, 0.6), "out")
        open_tip = (-0.165, -0.115)
        target = (base[8].x * 0.5 + open_tip[0] * 0.5,
                  base[8].y * 0.5 + open_tip[1] * 0.5)
        result = make_pose((0.06, 0.3, 0.5, 0.6), "target", target)
    elif name == "right_pinch":
        base = make_pose((0.9, 0.1, 0.9, 0.95), "out")
        target = (base[12].x + 0.006, base[12].y + 0.008)
        result = make_pose((0.9, 0.1, 0.9, 0.95), "target", target)
    else:
        raise KeyError(name)
    _CACHE[name] = result
    return result


def pinch_pose(level):
    """Смесь открытого и закрытого щипка: 0 — открыт, 1 — закрыт."""
    level = min(max(float(level), 0.0), 1.0)
    return blend(pose("pinch_open"), pose("pinch_closed"), level)


def blend(a, b, u):
    u = min(max(float(u), 0.0), 1.0)
    return [P(p.x + (q.x - p.x) * u, p.y + (q.y - p.y) * u)
            for p, q in zip(a, b, strict=True)]


def place(pts, wrist=(0.5, 0.8), scale=1.1):
    """Масштабирует позу и переносит запястье в нужную точку кадра."""
    return [P(wrist[0] + p.x * scale, wrist[1] + p.y * scale) for p in pts]


def jitter(pts, sigma=0.0015, seed=0):
    rnd = random.Random(seed)
    return [P(p.x + rnd.gauss(0, sigma), p.y + rnd.gauss(0, sigma)) for p in pts]
