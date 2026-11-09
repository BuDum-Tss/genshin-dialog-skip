"""
Genshin Skip — авто-пропуск диалогов в Genshin Impact (иконка в трее).

Работает поверх игры: захватывает кадр окна и нажимает клавиши. В память и
файлы игры не вмешивается.
  * «Скипать диалог» — видит золотой ромбик «продолжить» и жмёт пробел.
  * «Скипать выбор»  — в диалоге с вариантами ответа жмёт F (первый вариант).
"""
import threading
import ctypes
import time
from ctypes import wintypes

import mss
import numpy as np
import base64
import io
import cv2
import pystray
import templates
from PIL import Image, ImageDraw

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

# Область ромбика в долях клиентской части окна игры (x0, y0, x1, y1).
REGION = (0.490, 0.940, 0.518, 0.980)
WINDOW_TITLES = ("Genshin Impact", "Genshin", "Геншин")

VK_F8, VK_F9, VK_SPACE = 0x77, 0x78, 0x20


def is_gold(rgb: np.ndarray) -> np.ndarray:
    """Маска «золотых/оранжевых» пикселей ромбика."""
    r = rgb[..., 0].astype(int)
    g = rgb[..., 1].astype(int)
    b = rgb[..., 2].astype(int)
    return (r > 140) & (g > 100) & (b < 90) & (g * 100 > r * 58) & (g * 100 < r * 88) & (r - b > 90)


def gold_ratio(rgb: np.ndarray) -> float:
    return float(is_gold(rgb).mean())


def foreground_window():
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return hwnd, buf.value


def client_rect(hwnd):
    rc = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top


# --- нажатие пробела через SendInput со скан-кодом (работает в играх) ---
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def press_space():
    scan = 0x39
    for flags in (0x0008, 0x0008 | 0x0002):  # SCANCODE, затем SCANCODE|KEYUP
        inp = INPUT(1, _U(ki=KEYBDINPUT(0, scan, flags, 0, 0)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


THRESHOLD = 0.02
COOLDOWN = 0.30
F_REGION = (0.55, 0.30, 0.82, 0.92)     # где появляется список вариантов ответа
AUTO_REGION = (0.0, 0.0, 0.25, 0.12)    # кнопка «Авто» — есть только в диалогах
F_THRESHOLD = 0.75
AUTO_THRESHOLD = 0.7
state = {"paused": False, "skip_dialog": True, "skip_choice": True, "running": True}


def _tpl(b64):
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
    return np.asarray(img)


F_TPL, AUTO_TPL = _tpl(templates.F_PNG), _tpl(templates.AUTO_PNG)


def match(gray_frame, tpl, region, scale):
    h, w = gray_frame.shape
    x0, y0, x1, y1 = region
    sub = gray_frame[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
    t = cv2.resize(tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if abs(scale - 1) > 0.02 else tpl
    if sub.shape[0] < t.shape[0] or sub.shape[1] < t.shape[1]:
        return 0.0, (0, 0)
    res = cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    return float(mx), loc


def press_key(scan):
    for flags in (0x0008, 0x0008 | 0x0002):
        inp = INPUT(1, _U(ki=KEYBDINPUT(0, scan, flags, 0, 0)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)


def grab(sct, x, y, w, h, region):
    box = {"left": x + int(w * region[0]), "top": y + int(h * region[1]),
           "width": max(4, int(w * (region[2] - region[0]))),
           "height": max(4, int(h * (region[3] - region[1])))}
    return np.asarray(sct.grab(box))


def worker():
    with mss.mss() as sct:
        while state["running"]:
            try:
                hwnd, title = foreground_window()
                if (not state["paused"]) and any(t.lower() in title.lower() for t in WINDOW_TITLES):
                    x, y, w, h = client_rect(hwnd)
                    if w > 0 and h > 0:
                        if state["skip_dialog"]:
                            shot = grab(sct, x, y, w, h, REGION)[..., [2, 1, 0]]
                            if gold_ratio(shot) >= THRESHOLD:
                                press_space()
                                time.sleep(COOLDOWN)
                                continue
                        if state["skip_choice"]:
                            full = cv2.cvtColor(grab(sct, x, y, w, h, (0, 0, 1, 1)), cv2.COLOR_BGRA2GRAY)
                            sc = w / 1128.0
                            a, _ = match(full, AUTO_TPL, AUTO_REGION, sc)
                            if a >= AUTO_THRESHOLD:
                                f, _ = match(full, F_TPL, F_REGION, sc)
                                if f >= F_THRESHOLD:
                                    press_key(0x21)  # F
                                    time.sleep(0.7)
                                    continue
            except Exception:
                time.sleep(0.5)
            time.sleep(0.05)


def make_icon(active: bool, size: int = 64):
    k = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (240, 180, 55, 255) if active else (130, 130, 130, 255)
    pts = lambda *p: [(x * k, y * k) for x, y in p]
    d.polygon(pts((32, 4), (60, 32), (32, 60), (4, 32)), outline=c, width=max(1, round(5 * k)))
    d.polygon(pts((22, 36), (42, 36), (32, 46)), fill=c)
    return img


def main():
    icon = None

    def refresh():
        active = (not state["paused"]) and (state["skip_dialog"] or state["skip_choice"])
        icon.icon = make_icon(active)
        icon.title = "Skip диалога: работает" if active else "Skip диалога: остановлен"

    def flip(key):
        def f(i, item):
            state[key] = not state[key]
            refresh()
        return f

    def quit_(i, item):
        state["running"] = False
        i.stop()

    icon = pystray.Icon(
        "genshin_skip", make_icon(True), "Skip диалога: работает",
        menu=pystray.Menu(
            pystray.MenuItem("Режим скипа диалога", pystray.Menu(
                pystray.MenuItem("Скипать диалог", flip("skip_dialog"), checked=lambda i: state["skip_dialog"]),
                pystray.MenuItem("Скипать выбор (первый вариант)", flip("skip_choice"), checked=lambda i: state["skip_choice"]))),
            pystray.MenuItem("Остановить всё", flip("paused"), checked=lambda i: state["paused"], default=True),
            pystray.MenuItem("Выход", quit_)))
    threading.Thread(target=worker, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
