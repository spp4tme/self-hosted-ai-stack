"""
Jarvis v3 — Elite Edition
HUD cyberpunk, squelette néon, particules, TTS, IA contextuelle
"""

import cv2
import json
import math
import os
import sys
import time
import ctypes
import ctypes.wintypes
import base64
import threading
import urllib.request
import urllib.error
import http.client
import io
import logging
import collections
import random
import winsound
import numpy as np
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image as PILImage, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    HAS_MEDIAPIPE = True
except ImportError:
    print("[ERREUR] mediapipe non installe. Lancez: pip install mediapipe>=0.10")
    sys.exit(1)

try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
    _toaster = ToastNotifier()
except Exception:
    HAS_TOAST = False
    _toaster = None

try:
    from openwakeword.model import Model as OWWModel
    import pyaudio
    HAS_WAKE = True
except ImportError:
    HAS_WAKE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
JARVIS_DIR  = Path(__file__).parent
MODELS_DIR  = JARVIS_DIR / "models"
CONFIG_PATH = JARVIS_DIR / "config.json"
MODEL_PATH  = MODELS_DIR / "hand_landmarker.task"
MODEL_URL   = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis")

# ── Virtual Key codes ─────────────────────────────────────────────────────────
VK_PLAY_PAUSE = 0xB3
VK_NEXT       = 0xB0
VK_PREV       = 0xB1
VK_VOL_UP     = 0xAF
VK_VOL_DOWN   = 0xAE
VK_MUTE       = 0xAD
VK_WIN        = 0x5B
VK_ALT        = 0x12
VK_TAB        = 0x09
VK_F4         = 0x73
VK_D          = 0x44
VK_L          = 0x4C
KEYEVENTF_KEYUP = 0x0002
user32 = ctypes.windll.user32

# ── Mouse events ──────────────────────────────────────────────────────────────
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_WHEEL     = 0x0800

def key_press(vk):
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

def key_hold(vk):
    user32.keybd_event(vk, 0, 0, 0)

def key_release(vk):
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

def combo(mod, key, delay_ms=60):
    key_hold(mod)
    time.sleep(delay_ms / 1000)
    key_press(key)
    time.sleep(delay_ms / 1000)
    key_release(mod)

# ── Mode constants ────────────────────────────────────────────────────────────
MODE_MEDIA   = 0
MODE_PC      = 1
MODE_IA      = 2
MODE_POINTER = 3
MODE_NAMES   = ["MEDIA", "PC", "IA", "PTR"]

# ── Themes HUD par mode ───────────────────────────────────────────────────────
THEMES = {
    MODE_MEDIA: {
        "primary":  (0, 255, 128),    # vert néon
        "secondary":(0, 160, 80),
        "glow":     (0, 60, 30),
        "beep":     (880, 80),        # (fréquence Hz, durée ms)
        "icon":     "MEDIA",
    },
    MODE_PC: {
        "primary":  (80, 180, 255),   # bleu cyber
        "secondary":(40, 100, 200),
        "glow":     (10, 30, 80),
        "beep":     (660, 80),
        "icon":     "PC",
    },
    MODE_IA: {
        "primary":  (200, 80, 255),   # violet néon
        "secondary":(130, 40, 200),
        "glow":     (50, 10, 80),
        "beep":     (1100, 80),
        "icon":     "IA",
    },
    MODE_POINTER: {
        "primary":  (0, 230, 255),    # cyan électrique
        "secondary":(0, 140, 200),
        "glow":     (0, 40, 70),
        "beep":     (770, 70),
        "icon":     "PTR",
    },
}

# ── Gesture names ─────────────────────────────────────────────────────────────
G_STOP     = "STOP"
G_NAVIGATE = "NAVIGATE"
G_SELECT   = "SELECT"
G_VALIDATE = "VALIDATE"
G_SCROLL   = "SCROLL"
G_MODE     = "MODE"
G_NONE     = "NONE"

GESTURE_ICONS = {
    G_STOP:     "✋",
    G_NAVIGATE: "☝",
    G_SELECT:   "✊",
    G_VALIDATE: "👍",
    G_SCROLL:   "✌",
    G_MODE:     "🤘",
    G_NONE:     "·",
}

# ── Wake word state ───────────────────────────────────────────────────────────
_wake_active = False
_wake_until  = 0.0   # timestamp jusqu'auquel le mode actif dure

# ── TTS Engine (async queue) ──────────────────────────────────────────────────
_tts_queue: deque = deque()
_tts_lock  = threading.Lock()

def _tts_worker():
    if not HAS_TTS:
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 0.85)
        # Voix française si dispo
        voices = engine.getProperty("voices")
        for v in voices:
            if "french" in v.name.lower() or "fr" in v.id.lower():
                engine.setProperty("voice", v.id)
                break
        while True:
            text = None
            with _tts_lock:
                if _tts_queue:
                    text = _tts_queue.popleft()
            if text:
                engine.say(text)
                engine.runAndWait()
            else:
                time.sleep(0.05)
    except Exception as e:
        log.debug(f"[TTS] {e}")

def speak(text: str):
    if not HAS_TTS:
        return
    with _tts_lock:
        _tts_queue.clear()  # interrompt le précédent
        _tts_queue.append(text)

def play_beep(freq: int, duration_ms: int):
    try:
        threading.Thread(
            target=lambda: winsound.Beep(max(37, min(32767, freq)), duration_ms),
            daemon=True
        ).start()
    except Exception:
        pass

# ── Kalman Filter 1D ─────────────────────────────────────────────────────────
class KalmanFilter1D:
    def __init__(self, q: float = 0.0008, r: float = 0.004):
        self.q = q; self.r = r
        self.x = 0.5; self.p = 1.0

    def update(self, z: float) -> float:
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= (1.0 - k)
        return self.x


# ── Desktop AR Overlay (fenêtre transparente futuriste) ──────────────────────
class JarvisOverlay:
    _GWL_EXSTYLE       = -20
    _WS_EX_LAYERED     = 0x00080000
    _WS_EX_TRANSPARENT = 0x00000020

    def __init__(self):
        self.x = 0; self.y = 0
        self.action = ""; self.state = "idle"
        self.press_ratio = 0.0
        self.visible = False
        self._root = None; self._canvas = None
        self._lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def update(self, x: int, y: int, action: str = "", state: str = "idle",
               press_ratio: float = 0.0):
        with self._lock:
            self.x = x; self.y = y
            self.action = action; self.state = state
            self.press_ratio = press_ratio

    def show(self):
        with self._lock:
            self.visible = True

    def hide(self):
        with self._lock:
            self.visible = False

    def _make_clickthrough(self):
        try:
            hwnd = self._root.winfo_id()
            s = ctypes.windll.user32.GetWindowLongW(hwnd, self._GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, self._GWL_EXSTYLE,
                s | self._WS_EX_LAYERED | self._WS_EX_TRANSPARENT,
            )
        except Exception as e:
            log.debug(f"[Overlay] click-through: {e}")

    def _run(self):
        try:
            import tkinter as tk
        except ImportError:
            log.warning("[Overlay] tkinter absent — overlay désactivé")
            return
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        self._root = tk.Tk()
        self._root.title("JarvisHUD")
        self._root.geometry(f"{sw}x{sh}+0+0")
        self._root.overrideredirect(True)
        self._root.wm_attributes("-transparentcolor", "black")
        self._root.wm_attributes("-topmost", True)
        self._root.configure(bg="black")
        self._canvas = tk.Canvas(
            self._root, bg="black", highlightthickness=0, width=sw, height=sh
        )
        self._canvas.pack(fill="both", expand=True)
        self._make_clickthrough()
        self._tick()
        self._root.mainloop()

    def _tick(self):
        if not self._root:
            return
        c = self._canvas
        c.delete("all")
        with self._lock:
            vis    = self.visible
            x, y   = self.x, self.y
            action = self.action
            st     = self.state
        if vis:
            t = time.time()
            with self._lock:
                pr = self.press_ratio

            if st == "freeze":
                col, gcol = "#4a4a70", "#252540"
            elif st == "drag":
                col, gcol = "#0088ff", "#004488"
            elif st == "press":
                col, gcol = "#3355ff", "#112299"
            elif st == "click":
                pulse = abs(math.sin(t * 10))
                col   = f"#00{int(200 + 55 * pulse):02x}ff"
                gcol  = "#004488"
            elif st == "scroll":
                col, gcol = "#00ff88", "#005533"
            else:
                col, gcol = "#00e5ff", "#006688"

            # Anneaux pulsants de base
            for r_base, w_ring in ((52, 1), (36, 1), (22, 1)):
                r_now = r_base + int(3 * math.sin(t * 3 + r_base * 0.1))
                c.create_oval(x - r_now, y - r_now, x + r_now, y + r_now,
                              outline=gcol, width=w_ring)

            # Anneau de pression : se rétrécit quand le doigt s'approche du seuil
            # 0% → rayon 52, 100% → rayon 8 (sensation d'appui physique)
            if pr > 0.04:
                r_p = int(52 - 44 * pr)
                press_col = "#3355ff" if pr < 1.0 else "#00ff88"
                c.create_oval(x - r_p, y - r_p, x + r_p, y + r_p,
                              outline=press_col, width=2)

            # Crosshair
            sz, gap = 30, 8
            c.create_line(x - sz, y,  x - gap, y,  fill=col, width=2)
            c.create_line(x + gap, y, x + sz,  y,  fill=col, width=2)
            c.create_line(x, y - sz,  x, y - gap,  fill=col, width=2)
            c.create_line(x, y + gap, x, y + sz,   fill=col, width=2)

            # Ticks diagonaux sur l'anneau extérieur
            for a_deg in (45, 135, 225, 315):
                a   = math.radians(a_deg)
                r_i = 52
                c.create_line(
                    x + int((r_i - 7) * math.cos(a)), y + int((r_i - 7) * math.sin(a)),
                    x + int((r_i + 7) * math.cos(a)), y + int((r_i + 7) * math.sin(a)),
                    fill=col, width=1,
                )

            # Point central
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=col, outline="")

            # Label action (ombre 1px)
            if action:
                c.create_text(x + 40, y - 23, text=action, fill="#001020",
                              font=("Consolas", 11, "bold"), anchor="w")
                c.create_text(x + 39, y - 24, text=action, fill=col,
                              font=("Consolas", 11, "bold"), anchor="w")

            # Badge d'état
            badge = {"freeze": "■ FIGÉ", "drag": "◉ DRAG", "press": "▼ PRESS",
                     "click": "● CLIC",  "scroll": "⟺ SCROLL"}.get(st, "◉ PTR")
            c.create_text(x + 39, y - 8, text=badge, fill=gcol,
                          font=("Consolas", 9), anchor="w")

        self._root.after(16, self._tick)


# ── Pointer / Mouse controller ───────────────────────────────────────────────
class PointerController:
    SW        = ctypes.windll.user32.GetSystemMetrics(0)
    SH        = ctypes.windll.user32.GetSystemMetrics(1)
    DEAD_ZONE = 0.005

    # Zone active de la caméra → mappée à l'écran complet.
    # Seul le centre 76×84 % du cadre est utilisé : plus de précision,
    # plus besoin d'aller aux coins extrêmes de la caméra.
    AZ_X0, AZ_X1 = 0.12, 0.88
    AZ_Y0, AZ_Y1 = 0.08, 0.92

    # Seuils de la pression Z (index tip Z relatif au poignet)
    PRESS_FIRE    = 0.040   # profondeur pour déclencher le clic
    PRESS_RELEASE = 0.014   # doit revenir sous ce seuil avant la prochaine pression
    PRESS_CD      = 0.50    # cooldown entre deux pressions (secondes)
    PRESS_WARMUP  = 20      # frames pour initialiser la baseline Z

    def __init__(self, q: float = 0.0006, r: float = 0.003):
        self.kx = KalmanFilter1D(q=q,     r=r)
        self.ky = KalmanFilter1D(q=q,     r=r)
        self.kz = KalmanFilter1D(q=0.004, r=0.018)  # Z plus bruité
        self.px = 0.5; self.py = 0.5
        # Pression Z
        self.z_base    = None
        self.z_warmup  = 0
        self.z_depth   = 0.0   # positif = doigt poussé vers la caméra
        self.pressing  = False
        self.press_t   = 0.0
        # Drag / poing
        self.frozen    = False
        self.lock_move = False
        self.dragging  = False
        self.fist_held = False
        self.fist_t    = 0.0
        # Scroll
        self.scroll_ref = None
        # État général
        self.action = ""
        self.clicks = 0
        self._last_g = G_NONE

    @staticmethod
    def _remap(v: float, v0: float, v1: float) -> float:
        return max(0.0, min(1.0, (v - v0) / (v1 - v0)))

    def move(self, lm):
        # ── Z : profondeur du doigt (relatif au poignet, stable) ────────────
        z_raw = lm[8].z - lm[0].z
        z_s   = self.kz.update(z_raw)
        if self.z_warmup < self.PRESS_WARMUP:
            self.z_base   = z_s
            self.z_warmup += 1
        else:
            # baseline dérive lentement vers la position neutre courante
            self.z_base = 0.994 * self.z_base + 0.006 * z_s
        # profondeur positive = le doigt avance vers la caméra par rapport à la baseline
        self.z_depth = float(self.z_base - z_s)

        # ── X/Y : zone active + Kalman ──────────────────────────────────────
        ix_r = self._remap(lm[8].x, self.AZ_X0, self.AZ_X1)
        iy_r = self._remap(lm[8].y, self.AZ_Y0, self.AZ_Y1)
        if self.frozen or self.lock_move:
            self.kx.update(ix_r); self.ky.update(iy_r)
            return
        if abs(ix_r - self.px) < self.DEAD_ZONE and abs(iy_r - self.py) < self.DEAD_ZONE:
            self.kx.update(ix_r); self.ky.update(iy_r)
            return
        self.px = self.kx.update(ix_r)
        self.py = self.ky.update(iy_r)
        user32.SetCursorPos(
            max(0, min(self.SW - 1, int(self.px * self.SW))),
            max(0, min(self.SH - 1, int(self.py * self.SH))),
        )

    def process(self, lm, gesture: str):
        now = time.time()

        # ── Pression Z (index étendu = G_NAVIGATE) = clic naturel ───────────
        # Le doigt "appuie" vers la caméra comme sur un écran virtuel.
        if gesture == G_NAVIGATE and self.z_warmup >= self.PRESS_WARMUP:
            if not self.pressing and self.z_depth > self.PRESS_FIRE:
                self.pressing = True   # début d'appui détecté
            elif self.pressing and self.z_depth < self.PRESS_RELEASE and now > self.press_t:
                # Relâchement → clic (comme un vrai bouton physique)
                self.pressing = False
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.035)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.clicks += 1
                self.action  = f"PRESS ×{self.clicks}"
                play_beep(1000, 35)
                self.press_t = now + self.PRESS_CD
        else:
            self.pressing = False

        # ── Poing court (G_SELECT < 400ms) = clic de secours ────────────────
        # Poing long (> 400ms) = drag
        if gesture == G_SELECT:
            self.lock_move = True
            if not self.fist_held:
                self.fist_held = True; self.fist_t = now; self.dragging = False
            elif now - self.fist_t > 0.40 and not self.dragging:
                self.dragging  = True
                self.lock_move = False
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self.action = "DRAG ▼"
        else:
            if self.fist_held:
                if self.dragging:
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.action   = "DROP ✓"
                    self.dragging = False
                else:
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.035)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.clicks += 1
                    self.action  = f"CLIC ×{self.clicks}"
                    play_beep(900, 30)
                self.fist_held = False
                self.lock_move = False

        # ── Pouce (G_VALIDATE) = clic droit ────────────────────────────────
        if gesture == G_VALIDATE and self._last_g != G_VALIDATE:
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.035)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            self.action = "CLIC DROIT"
            play_beep(700, 30)

        # ── Paume (G_STOP) = figer / libérer ───────────────────────────────
        if gesture == G_STOP and self._last_g != G_STOP:
            self.frozen = not self.frozen
            self.action = "■ FIGÉ" if self.frozen else "▶ LIBRE"
            play_beep(550 if self.frozen else 820, 50)

        # ── V / Paix (G_SCROLL) = molette ──────────────────────────────────
        if gesture == G_SCROLL:
            self.lock_move = True
            my = lm[12].y
            if self.scroll_ref is None:
                self.scroll_ref = my
            delta = self.scroll_ref - my
            if abs(delta) > 0.010:
                user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta * 2200), 0)
                self.scroll_ref = my
                self.action     = f"SCROLL {'↑' if delta > 0 else '↓'}"
        else:
            if self._last_g == G_SCROLL:
                self.lock_move = False
            self.scroll_ref = None

        self._last_g = gesture

    @property
    def press_ratio(self) -> float:
        """0→1 : progression vers le seuil de pression (feedback visuel)."""
        return min(1.0, self.z_depth / self.PRESS_FIRE) if self.PRESS_FIRE > 0 else 0.0

    @property
    def overlay_state(self) -> str:
        if self.frozen:              return "freeze"
        if self.dragging:            return "drag"
        if self.pressing:            return "press"
        if self.fist_held:           return "click"
        if self._last_g == G_SCROLL: return "scroll"
        return "idle"

    @property
    def screen_pos(self):
        return (
            max(0, min(self.SW - 1, int(self.px * self.SW))),
            max(0, min(self.SH - 1, int(self.py * self.SH))),
        )


def draw_pointer_overlay(frame, pts, ctrl):
    """Réticule + jauge de pression dans le flux caméra."""
    h, w = frame.shape[:2]
    ix, iy = pts[8]

    if ctrl.frozen:     c = (90, 90, 110)
    elif ctrl.dragging: c = (255, 120, 0)
    elif ctrl.pressing: c = (50, 50, 255)
    elif ctrl.fist_held:c = (0, 200, 255)
    else:               c = (0, 230, 255)

    # Réticule sur l'index
    s = 18
    cv2.line(frame, (ix - s, iy), (ix + s, iy), c, 2, cv2.LINE_AA)
    cv2.line(frame, (ix, iy - s), (ix, iy + s), c, 2, cv2.LINE_AA)
    cv2.circle(frame, (ix, iy), 9, c, 2, cv2.LINE_AA)
    cv2.circle(frame, (ix, iy), 2, c, -1, cv2.LINE_AA)

    # Jauge de pression Z (barre sous le réticule)
    ratio = ctrl.press_ratio
    bw, bh = 90, 5
    bx, by = ix - bw // 2, iy + 20
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (25, 25, 35), -1)
    if ratio > 0.01:
        fill = int(bw * ratio)
        # bleu → rouge au fur et à mesure de l'appui
        fc = (0, int(220 * (1 - ratio)), int(220 * ratio + 35))
        if ctrl.pressing:
            fc = (0, 230, 80)   # vert : appui confirmé
        cv2.rectangle(frame, (bx, by), (bx + fill, by + bh), fc, -1)
    cv2.putText(frame, "Z", (bx - 14, by + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, c, 1, cv2.LINE_AA)

    # Zone active (cadre discret au 1er frame puis invisible)
    if ctrl.z_warmup < ctrl.PRESS_WARMUP:
        azx0 = int(ctrl.AZ_X0 * w); azx1 = int(ctrl.AZ_X1 * w)
        azy0 = int(ctrl.AZ_Y0 * h); azy1 = int(ctrl.AZ_Y1 * h)
        cv2.rectangle(frame, (azx0, azy0), (azx1, azy1), (40, 40, 55), 1)

    sx, sy = ctrl.screen_pos
    info = f"{'■' if ctrl.frozen else '◉'} ({sx},{sy})"
    if ctrl.action:
        info += f"  {ctrl.action}"
    cv2.putText(frame, info, (12, h - 44),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, c, 1, cv2.LINE_AA)


# ── Wake word listener ────────────────────────────────────────────────────────
def _wake_listener():
    global _wake_active, _wake_until
    if not HAS_WAKE:
        log.info("[WAKE] openwakeword absent — pip install openwakeword pyaudio")
        return
    try:
        model = OWWModel(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    except Exception as e:
        log.warning(f"[WAKE] Modèle hey_jarvis non disponible: {e}")
        return
    try:
        pa     = pyaudio.PyAudio()
        stream = pa.open(rate=16000, channels=1, format=pyaudio.paInt16,
                         input=True, frames_per_buffer=1280)
    except Exception as e:
        log.warning(f"[WAKE] Micro inaccessible: {e}")
        return
    log.info("[WAKE] ◉ En écoute — 'Hey Jarvis'")
    while True:
        try:
            chunk = stream.read(1280, exception_on_overflow=False)
            audio = np.frombuffer(chunk, dtype=np.int16)
            pred  = model.predict(audio)
            for word, score in pred.items():
                if score > 0.5:
                    log.info(f"[WAKE] Activé! {word} score={score:.2f}")
                    _wake_active = True
                    _wake_until  = time.time() + 8.0
                    play_beep(1320, 90)
                    time.sleep(0.06)
                    play_beep(1600, 70)
                    speak("Oui ?")
                    break
        except Exception:
            pass

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "cooldown": 1.5,
    "hold_duration": 2.0,
    "notifications_enabled": True,
    "camera_index": 0,
    "preview_window": True,
    "auto_mode": True,
    "n8n_url": "http://localhost:5678",
    "ollama_url": "http://localhost:11434",
    "default_model": "deepseek-r1:14b",
    "vision_model": "llava",
    "embed_model": "nomic-embed-text",
    "default_mode": 0,
    "tts_enabled": True,
    "particles_enabled": True,
    "glow_enabled": True,
    "trail_enabled": True,
    "window_width": 960,
    "window_height": 560,
    "wake_word_enabled": True,
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            log.warning(f"Config non lisible ({e})")
    return cfg

# ── Model download ────────────────────────────────────────────────────────────
def ensure_model():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists():
        return
    log.info(f"Téléchargement du modèle MediaPipe → {MODEL_PATH}")
    try:
        def _prog(b, bs, ts):
            print(f"\r  {min(100, b*bs*100//ts)}%   ", end="", flush=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, _prog)
        print()
    except Exception as e:
        log.error(f"Téléchargement échoué: {e}")
        sys.exit(1)

# ── Gesture detection ─────────────────────────────────────────────────────────
def _hand_scale(lm):
    return math.dist((lm[0].x, lm[0].y), (lm[9].x, lm[9].y)) + 1e-8

def fingers_extended(lm):
    scale = _hand_scale(lm)
    v1 = (lm[3].x - lm[2].x, lm[3].y - lm[2].y)
    v2 = (lm[4].x - lm[3].x, lm[4].y - lm[3].y)
    n1 = math.sqrt(v1[0]**2 + v1[1]**2) + 1e-8
    n2 = math.sqrt(v2[0]**2 + v2[1]**2) + 1e-8
    thumb_cos = (v1[0]*v2[0] + v1[1]*v2[1]) / (n1 * n2)
    thumb_gap = math.dist((lm[4].x, lm[4].y), (lm[5].x, lm[5].y)) / scale
    thumb = (thumb_cos > 0.5) and (thumb_gap > 0.28)

    def ext(tip, pip, mcp):
        seg = abs(lm[pip].y - lm[mcp].y) + abs(lm[pip].x - lm[mcp].x) + 1e-8
        return (lm[pip].y - lm[tip].y) > seg * 0.25

    return thumb, ext(8,6,5), ext(12,10,9), ext(16,14,13), ext(20,18,17)

def classify_raw(lm):
    thumb, index, middle, ring, pinky = fingers_extended(lm)
    if index and pinky and not middle and not ring and not thumb:
        return G_MODE
    if thumb and index and middle and ring and pinky:
        return G_STOP
    if thumb and not index and not middle and not ring and not pinky:
        return G_VALIDATE
    if not index and not middle and not ring and not pinky:
        return G_SELECT
    if index and not middle and not ring and not pinky:
        return G_NAVIGATE
    if index and middle and not ring and not pinky:
        return G_SCROLL
    return G_NONE

# ── Temporal filter ───────────────────────────────────────────────────────────
class GestureFilter:
    BUFFER_LEN    = 8
    CONFIRM_RATIO = 0.75

    def __init__(self):
        self._buf = deque(maxlen=self.BUFFER_LEN)

    def push(self, raw):
        self._buf.append(raw)
        if len(self._buf) < self.BUFFER_LEN // 2:
            return G_NONE
        counts = Counter(self._buf)
        top, cnt = counts.most_common(1)[0]
        return top if cnt / len(self._buf) >= self.CONFIRM_RATIO else G_NONE

    def reset(self):
        self._buf.clear()

    @property
    def confidence(self):
        if not self._buf:
            return 0.0
        return Counter(self._buf).most_common(1)[0][1] / len(self._buf)

    @property
    def dominant(self):
        return Counter(self._buf).most_common(1)[0][0] if self._buf else G_NONE

# ── Particle System ───────────────────────────────────────────────────────────
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "r", "color")

    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 5.0)
        self.x = float(x)
        self.y = float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.r = random.randint(2, 5)
        self.color = color

    def update(self, dt=0.033):
        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.92
        self.vy *= 0.92
        self.life -= dt * 2.5

    @property
    def alive(self):
        return self.life > 0


class ParticleSystem:
    def __init__(self, max_particles=120):
        self._particles: list[Particle] = []
        self._max = max_particles

    def burst(self, x, y, color, count=30):
        room = self._max - len(self._particles)
        for _ in range(min(count, room)):
            self._particles.append(Particle(x, y, color))

    def update_and_draw(self, frame, dt=0.033):
        surviving = []
        for p in self._particles:
            p.update(dt)
            if p.alive:
                alpha = max(0.0, p.life)
                c = tuple(int(ch * alpha) for ch in p.color)
                ix, iy = int(p.x), int(p.y)
                h, w = frame.shape[:2]
                if 0 <= ix < w and 0 <= iy < h:
                    cv2.circle(frame, (ix, iy), p.r, c, -1)
                surviving.append(p)
        self._particles = surviving

# ── Hand connections ──────────────────────────────────────────────────────────
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

FINGERTIPS = [4, 8, 12, 16, 20]

# ── Glow rendering ────────────────────────────────────────────────────────────
def draw_hand_glow(frame, pts, color, enabled=True):
    """Squelette néon avec halo lumineux multi-couche."""
    h, w = frame.shape[:2]
    c = color  # BGR

    if enabled:
        glow = np.zeros_like(frame, dtype=np.uint8)
        for a, b in HAND_CONNECTIONS:
            cv2.line(glow, pts[a], pts[b], c, 8)
        for i, (x, y) in enumerate(pts):
            r = 12 if i in FINGERTIPS else 8
            cv2.circle(glow, (x, y), r, c, -1)
        glow = cv2.GaussianBlur(glow, (31, 31), 0)
        frame[:] = cv2.add(frame, glow)

    # Lignes principales
    for a, b in HAND_CONNECTIONS:
        bright = tuple(min(255, int(ch * 1.4)) for ch in c)
        cv2.line(frame, pts[a], pts[b], bright, 2, cv2.LINE_AA)

    # Joints
    for i, (x, y) in enumerate(pts):
        if i in FINGERTIPS:
            cv2.circle(frame, (x, y), 6, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 6, c, 2, cv2.LINE_AA)
        else:
            cv2.circle(frame, (x, y), 4, c, -1, cv2.LINE_AA)

# ── Scan ring ─────────────────────────────────────────────────────────────────
_scan_angle = 0.0

def draw_scan_ring(frame, cx, cy, radius, color, confidence):
    global _scan_angle
    _scan_angle = (_scan_angle + 3.5) % 360
    base_alpha = max(0.2, confidence * 0.6)
    base_c = tuple(int(ch * base_alpha) for ch in color)
    cv2.circle(frame, (cx, cy), radius, base_c, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), radius + 4, tuple(int(ch * base_alpha * 0.4) for ch in color), 1, cv2.LINE_AA)

    for i in range(90):
        a = math.radians(_scan_angle + i)
        alpha = (i / 90.0) ** 0.5
        c = tuple(int(ch * alpha * min(1.0, confidence + 0.3)) for ch in color)
        x = int(cx + radius * math.cos(a))
        y = int(cy + radius * math.sin(a))
        if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
            cv2.circle(frame, (x, y), 2, c, -1, cv2.LINE_AA)

    # Croix centrale (petit réticule)
    s = 8
    dim_c = tuple(int(ch * 0.5) for ch in color)
    cv2.line(frame, (cx - s, cy), (cx + s, cy), dim_c, 1, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - s), (cx, cy + s), dim_c, 1, cv2.LINE_AA)

# ── Vignette ──────────────────────────────────────────────────────────────────
def apply_vignette(frame):
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    vignette = np.clip(1.0 - dist * 0.55, 0.45, 1.0)
    frame[:] = (frame * vignette[:, :, np.newaxis]).astype(np.uint8)

# ── Corner HUD brackets ───────────────────────────────────────────────────────
def draw_corners(frame, color, size=30, thickness=2):
    h, w = frame.shape[:2]
    c = color
    corners = [(0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)]
    for x, y, dx, dy in corners:
        cv2.line(frame, (x, y), (x + dx * size, y), c, thickness, cv2.LINE_AA)
        cv2.line(frame, (x, y), (x, y + dy * size), c, thickness, cv2.LINE_AA)
        cv2.circle(frame, (x, y), 3, (255, 255, 255), -1)

# ── Gesture history ───────────────────────────────────────────────────────────
_gesture_history: deque = deque(maxlen=6)

def record_gesture(gesture: str):
    _gesture_history.append((gesture, time.time()))

# ── Rounded rectangle ─────────────────────────────────────────────────────────
def draw_rounded_rect(frame, x1, y1, x2, y2, color, alpha=0.55, radius=10):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(overlay, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    for cx, cy in [(x1+radius, y1+radius),(x2-radius, y1+radius),
                   (x1+radius, y2-radius),(x2-radius, y2-radius)]:
        cv2.circle(overlay, (cx, cy), radius, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

# ── Confidence ring ───────────────────────────────────────────────────────────
def draw_confidence_ring(frame, cx, cy, confidence, color, radius=22):
    cv2.circle(frame, (cx, cy), radius, (40, 40, 40), 3, cv2.LINE_AA)
    if confidence > 0.01:
        angle = int(360 * confidence)
        for i in range(angle):
            a = math.radians(i - 90)
            alpha = 0.5 + 0.5 * confidence
            c = tuple(int(ch * alpha) for ch in color)
            x = int(cx + radius * math.cos(a))
            y = int(cy + radius * math.sin(a))
            if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
                cv2.circle(frame, (x, y), 2, c, -1)

# ── FPS counter ───────────────────────────────────────────────────────────────
_fps_buf = deque(maxlen=30)
_last_fps_t = time.time()

def update_fps():
    global _last_fps_t
    now = time.time()
    _fps_buf.append(now - _last_fps_t)
    _last_fps_t = now
    if len(_fps_buf) < 2:
        return 0.0
    return 1.0 / (sum(_fps_buf) / len(_fps_buf))

# ── Main OSD ──────────────────────────────────────────────────────────────────
def draw_osd(frame, state, confirmed, dominant, confidence, hold_progress, fps):
    h, w = frame.shape[:2]
    mode  = state["mode"]
    theme = THEMES[mode]
    color = theme["primary"]
    dim   = theme["secondary"]
    name  = theme["icon"]

    # ── Top bar ───────────────────────────────────────────────────────────────
    draw_rounded_rect(frame, 0, 0, w, 58, (10, 10, 15), alpha=0.75, radius=0)

    # Mode badge
    draw_rounded_rect(frame, 6, 6, 126, 52, dim, alpha=0.9, radius=8)
    cv2.putText(frame, name, (14, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    # Ligne de séparation colorée sous mode badge
    cv2.line(frame, (6, 52), (126, 52), color, 2, cv2.LINE_AA)

    # Gesture name
    if confirmed != G_NONE:
        gname = confirmed
        gcol  = color
        gsize = 1.0
    elif dominant != G_NONE:
        gname = dominant
        gcol  = (80, 80, 80)
        gsize = 0.85
    else:
        gname = "STANDBY"
        gcol  = (50, 50, 60)
        gsize = 0.75

    cv2.putText(frame, gname, (140, 40),
                cv2.FONT_HERSHEY_SIMPLEX, gsize, gcol, 2, cv2.LINE_AA)

    # Confidence ring inline
    draw_confidence_ring(frame, w - 120, 30, confidence, color, radius=18)
    pct_text = f"{int(confidence * 100)}%"
    cv2.putText(frame, pct_text, (w - 132, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

    # Wake word indicator
    if _wake_active and time.time() < _wake_until:
        pulse = int(abs(math.sin(time.time() * 5)) * 200) + 55
        wc = (0, pulse, int(pulse * 0.5))
        cv2.circle(frame, (w - 160, 16), 5, wc, -1, cv2.LINE_AA)
        cv2.putText(frame, "WAKE", (w - 152, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, wc, 1, cv2.LINE_AA)
    elif HAS_WAKE:
        cv2.circle(frame, (w - 160, 16), 3, (30, 60, 40), -1, cv2.LINE_AA)

    # FPS
    cv2.putText(frame, f"{fps:.0f}fps", (w - 72, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 80), 1, cv2.LINE_AA)

    # Heure
    ts = datetime.now().strftime("%H:%M:%S")
    cv2.putText(frame, ts, (w - 80, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 100, 120), 1, cv2.LINE_AA)

    # ── Hold progress (barre pleine largeur animée) ────────────────────────────
    if hold_progress > 0.02:
        bh = 5
        cv2.rectangle(frame, (0, 58), (w, 58 + bh), (25, 25, 35), -1)
        filled = int(w * min(hold_progress, 1.0))
        cv2.rectangle(frame, (0, 58), (filled, 58 + bh), color, -1)
        glow = np.zeros((bh, w, 3), dtype=np.uint8)
        glow[:, :filled] = color
        glow = cv2.GaussianBlur(glow, (1, 7), 0)
        roi = frame[58:58+bh, 0:w]
        frame[58:58+bh, 0:w] = cv2.add(roi, glow)

    # ── Bottom bar ────────────────────────────────────────────────────────────
    draw_rounded_rect(frame, 0, h - 68, w, h, (10, 10, 15), alpha=0.75, radius=0)

    # Dernière action
    last = state.get("last_action", "")
    if last:
        cv2.putText(frame, f"▶  {last}", (12, h - 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 1, cv2.LINE_AA)

    # Historique des gestes (icônes texte)
    hist_x = 12
    now = time.time()
    for g, t in list(_gesture_history):
        age = now - t
        if age > 8:
            continue
        alpha_fade = max(0.0, 1.0 - age / 8.0)
        fade_c = tuple(int(ch * alpha_fade) for ch in color)
        cv2.putText(frame, GESTURE_ICONS.get(g, "?"), (hist_x, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, fade_c, 1, cv2.LINE_AA)
        hist_x += 40

    # Touches
    cv2.putText(frame, "Q:quit  M:mode  S:speak  1/2/3:mode direct",
                (hist_x + 10, h - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (55, 55, 65), 1, cv2.LINE_AA)

    # ── JARVIS watermark (idle) ────────────────────────────────────────────────
    if confirmed == G_NONE and dominant == G_NONE:
        text_size = cv2.getTextSize("JARVIS", cv2.FONT_HERSHEY_SIMPLEX, 2.5, 1)[0]
        tx = (w - text_size[0]) // 2
        ty = h // 2 + 20
        cv2.putText(frame, "JARVIS", (tx + 2, ty + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.5, (20, 20, 25), 1, cv2.LINE_AA)
        dim_wm = tuple(int(ch * 0.12) for ch in color)
        cv2.putText(frame, "JARVIS", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.5, dim_wm, 1, cv2.LINE_AA)

# ── Trail (palm positions) ────────────────────────────────────────────────────
_trail: deque = deque(maxlen=25)

def draw_trail(frame, color):
    pts = list(_trail)
    for i, (x, y) in enumerate(pts):
        alpha = (i / max(1, len(pts))) ** 2
        r = max(1, int(4 * alpha))
        c = tuple(int(ch * alpha * 0.7) for ch in color)
        cv2.circle(frame, (x, y), r, c, -1, cv2.LINE_AA)

# ── Auto window detection ─────────────────────────────────────────────────────
MEDIA_KEYWORDS = ["spotify","youtube","vlc","netflix","prime video","deezer",
                  "tidal","soundcloud","twitch","plex","jellyfin","groove"]
PC_KEYWORDS    = ["code","vscode","powershell","cmd","terminal","notepad++",
                  "pycharm","intellij","sublime","cursor","visual studio"]

def get_active_window_title():
    try:
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(n)
        user32.GetWindowTextW(hwnd, buf, n)
        return buf.value.lower()
    except Exception:
        return ""

def suggest_mode_from_window(title):
    for kw in MEDIA_KEYWORDS:
        if kw in title:
            return MODE_MEDIA
    for kw in PC_KEYWORDS:
        if kw in title:
            return MODE_PC
    return None

def auto_mode_thread(state, cfg):
    while state.get("running", True):
        time.sleep(3)
        if not cfg.get("auto_mode", True):
            continue
        if time.time() - state.get("manual_switch", 0) < 30:
            continue
        title = get_active_window_title()
        s = suggest_mode_from_window(title)
        if s is not None and s != state["mode"]:
            log.info(f"[Auto] {MODE_NAMES[state['mode']]} → {MODE_NAMES[s]}")
            state["mode"] = s

# ── Screenshot + Ollama vision ────────────────────────────────────────────────
def screenshot_and_analyze(prompt, cfg, callback=None):
    def _w():
        try:
            if not HAS_PIL:
                speak("Pillow non disponible")
                return
            img = ImageGrab.grab()
            w, h_i = img.size
            if w > 1280:
                img = img.resize((1280, int(h_i * 1280 / w)))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            payload = json.dumps({
                "model": cfg.get("vision_model", "llava"),
                "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                f"{cfg.get('ollama_url','http://localhost:11434')}/api/chat",
                data=payload, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read())
                answer = data.get("message", {}).get("content", "Pas de réponse")
                log.info(f"[Vision] {answer[:300]}")
                if callback:
                    callback(answer[:120])
                speak(answer[:200])
        except Exception as e:
            log.error(f"[Vision] {e}")
    threading.Thread(target=_w, daemon=True).start()

def ai_quick_query(prompt, cfg, callback=None):
    def _w():
        try:
            payload = json.dumps({
                "model": cfg.get("default_model", "deepseek-r1:14b"),
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{cfg.get('ollama_url','http://localhost:11434')}/api/chat",
                data=payload, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
                answer = data.get("message", {}).get("content", "")
                log.info(f"[IA] {answer[:300]}")
                if callback:
                    callback(answer[:120])
                speak(answer[:250])
        except Exception as e:
            log.error(f"[IA] {e}")
    threading.Thread(target=_w, daemon=True).start()

def call_n8n(gesture, cfg):
    def _w():
        try:
            payload = json.dumps({"gesture": gesture, "mode": "IA"}).encode()
            req = urllib.request.Request(
                f"{cfg.get('n8n_url','http://localhost:5678')}/webhook/jarvis",
                data=payload, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                ans = data.get("response", "")
                if ans:
                    log.info(f"[n8n] {ans[:200]}")
                    speak(ans[:150])
        except Exception as e:
            log.error(f"[n8n] {e}")
    threading.Thread(target=_w, daemon=True).start()

# ── Action dispatch ───────────────────────────────────────────────────────────
def execute_primary(gesture, mode, cfg, state):
    if mode == MODE_MEDIA:
        if gesture == G_STOP:     key_press(VK_PLAY_PAUSE); return "Pause / Lecture"
        if gesture == G_NAVIGATE: key_press(VK_NEXT);       return "Piste suivante"
        if gesture == G_SELECT:   key_press(VK_PREV);       return "Piste précédente"
        if gesture == G_VALIDATE: key_press(VK_VOL_UP);     return "Volume +"
        if gesture == G_SCROLL:   key_press(VK_VOL_DOWN);   return "Volume -"

    elif mode == MODE_PC:
        if gesture == G_STOP:     combo(VK_WIN, VK_D);      return "Bureau"
        if gesture == G_NAVIGATE: combo(VK_ALT, VK_TAB);    return "Fenêtre suivante"
        if gesture == G_SELECT:   combo(VK_ALT, VK_F4);     return "Fermer fenêtre"
        if gesture == G_VALIDATE: key_press(VK_WIN);         return "Menu Démarrer"
        if gesture == G_SCROLL:   combo(VK_WIN, VK_TAB);    return "Vue tâches"

    elif mode == MODE_IA:
        def set_status(txt): state["last_action"] = txt

        if gesture == G_STOP:
            state["last_action"] = "Analyse en cours…"
            screenshot_and_analyze(
                "Tu es Jarvis, un assistant IA. Décris en 2 phrases ce que tu vois sur cet écran et propose une action utile.",
                cfg, callback=set_status
            )
            return "Analyse écran…"

        if gesture == G_NAVIGATE:
            title = get_active_window_title()
            prompt = f"Fenêtre active: '{title}'. Quelle est la meilleure commande ou action rapide que je peux faire maintenant ? Réponds en 1 phrase."
            state["last_action"] = "IA réfléchit…"
            ai_quick_query(prompt, cfg, callback=set_status)
            return "Conseil IA…"

        if gesture == G_SELECT:
            call_n8n("SELECT", cfg)
            return "Résumé projet"

        if gesture == G_VALIDATE:
            ai_quick_query(
                "Donne-moi 3 idées créatives pour améliorer ma productivité avec une IA locale. Format: • idée courte",
                cfg, callback=set_status
            )
            return "Idées IA…"

        if gesture == G_SCROLL:
            call_n8n("SCROLL", cfg)
            return "Nouvelles IA…"

    return ""

def execute_secondary(gesture, mode, cfg, state):
    if mode == MODE_MEDIA and gesture == G_STOP:
        key_press(VK_MUTE); return "Muet"
    if mode == MODE_PC and gesture == G_STOP:
        combo(VK_WIN, VK_L); return "Écran verrouillé"
    if mode == MODE_IA and gesture == G_NAVIGATE:
        screenshot_and_analyze(
            "Analyse cet écran et donne-moi les 3 choses les plus importantes que je devrais faire maintenant.",
            cfg
        )
        return "Analyse approfondie…"
    if mode == MODE_IA and gesture == G_VALIDATE:
        screenshot_and_analyze(
            "Regarde cet écran et explique-moi en détail ce qui est affiché, step by step.",
            cfg
        )
        return "Explication détaillée…"
    return ""

# ── Notifications ─────────────────────────────────────────────────────────────
def notify(title, msg, cfg):
    if not cfg.get("notifications_enabled", True):
        return
    if HAS_TOAST and _toaster:
        try:
            _toaster.show_toast(title, msg, duration=2, threaded=True)
        except Exception:
            pass

# ── Tray ──────────────────────────────────────────────────────────────────────
def make_tray_icon(mode):
    size = 64
    img  = PILImage.new("RGB", (size, size), (20, 20, 25))
    draw = ImageDraw.Draw(img)
    c_map = {MODE_MEDIA:(0,200,100), MODE_PC:(60,140,220), MODE_IA:(180,60,220)}
    c = c_map.get(mode, (200,200,200))
    draw.ellipse([8, 8, size-8, size-8], fill=c)
    return img

class TrayManager:
    def __init__(self, state, cfg):
        self.state = state
        self.cfg   = cfg
        self.icon  = None
        if not HAS_TRAY: return
        self._build()

    def _build(self):
        def set_mode(m):
            def _fn(icon, item):
                self.state["mode"] = m
                self.state["manual_switch"] = time.time()
                self._update_icon()
            return _fn
        menu = pystray.Menu(
            pystray.MenuItem("MEDIA", set_mode(MODE_MEDIA)),
            pystray.MenuItem("PC",    set_mode(MODE_PC)),
            pystray.MenuItem("IA",    set_mode(MODE_IA)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", lambda i, it: (self.state.__setitem__("running", False), i.stop())),
        )
        self.icon = pystray.Icon("Jarvis", make_tray_icon(self.state["mode"]), "Jarvis v3", menu)

    def start(self):
        if self.icon:
            threading.Thread(target=self.icon.run, daemon=True).start()

    def update(self, mode):
        if self.icon:
            self.icon.icon = make_tray_icon(mode)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    ensure_model()

    log.info("╔══════════════════════════════╗")
    log.info("║   JARVIS v3 — Elite Edition  ║")
    log.info("╚══════════════════════════════╝")
    log.info(f"TTS: {'✓' if HAS_TTS else '✗'}  Particules: {'✓' if cfg.get('particles_enabled') else '✗'}  Glow: {'✓' if cfg.get('glow_enabled') else '✗'}")
    log.info("Touches: Q=quit  M=mode  S=parler  1/2/3=mode direct")

    # TTS thread
    if HAS_TTS and cfg.get("tts_enabled", True):
        threading.Thread(target=_tts_worker, daemon=True).start()
        speak("Jarvis en ligne")

    # Wake word thread
    if cfg.get("wake_word_enabled", True):
        threading.Thread(target=_wake_listener, daemon=True).start()

    state = {
        "mode":          cfg.get("default_mode", MODE_MEDIA),
        "running":       True,
        "manual_switch": 0.0,
        "last_action":   "Jarvis prêt",
    }

    tray = TrayManager(state, cfg)
    tray.start()

    if cfg.get("auto_mode", True):
        threading.Thread(target=auto_mode_thread, args=(state, cfg), daemon=True).start()

    # MediaPipe
    base_opts = mp_python.BaseOptions(model_asset_path=str(MODEL_PATH))
    opts = mp_vision.HandLandmarkerOptions(
        base_options=base_opts,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.70,
        min_hand_presence_confidence=0.65,
        min_tracking_confidence=0.55,
    )
    detector = mp_vision.HandLandmarker.create_from_options(opts)

    cam_idx = cfg.get("camera_index", 0)
    cap = cv2.VideoCapture(cam_idx)
    if not cap.isOpened():
        log.error(f"Impossible d'ouvrir la caméra {cam_idx}")
        sys.exit(1)

    W = cfg.get("window_width",  960)
    H = cfg.get("window_height", 540)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_FPS, 30)
    log.info(f"Caméra {cam_idx} ouverte ({W}×{H})")

    preview    = cfg.get("preview_window", True)
    particles  = cfg.get("particles_enabled", True)
    glow_on    = cfg.get("glow_enabled", True)
    trail_on   = cfg.get("trail_enabled", True)
    gf            = GestureFilter()
    ps            = ParticleSystem(max_particles=150)
    pointer_ctrl = PointerController(
        q = cfg.get("pointer_kalman_q", 0.0008),
        r = cfg.get("pointer_kalman_r", 0.004),
    )
    overlay = JarvisOverlay()
    overlay.start()
    ts_origin  = time.monotonic()
    cooldown   = cfg.get("cooldown", 1.5)
    hold_dur   = cfg.get("hold_duration", 2.0)

    last_confirmed    = G_NONE
    last_exec_gesture = G_NONE
    last_action_t     = 0.0
    hold_start        = 0.0
    hold_fired        = False
    prev_frame_t      = time.time()

    if preview:
        cv2.namedWindow("Jarvis Elite", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Jarvis Elite", W, H)

    try:
        while state["running"]:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            now   = time.time()
            dt    = now - prev_frame_t
            prev_frame_t = now
            fps   = update_fps()

            # Reset wake word state si expiré
            global _wake_active
            if _wake_active and now > _wake_until:
                _wake_active = False

            # Resize si besoin
            fh, fw = frame.shape[:2]
            if fw != W or fh != H:
                frame = cv2.resize(frame, (W, H))

            # Vignette
            apply_vignette(frame)

            # Détection
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms  = int((time.monotonic() - ts_origin) * 1000)
            result = detector.detect_for_video(mp_img, ts_ms)

            hold_prog = 0.0
            mode      = state["mode"]
            theme     = THEMES[mode]
            color     = theme["primary"]

            # Sync overlay with pointer mode
            if mode == MODE_POINTER and not overlay.visible:
                overlay.show()
            elif mode != MODE_POINTER and overlay.visible:
                overlay.hide()

            if result.hand_landmarks:
                lm  = result.hand_landmarks[0]
                raw = classify_raw(lm)

                confirmed  = gf.push(raw)
                dominant   = gf.dominant
                confidence = gf.confidence

                # Pixels
                fh2, fw2 = frame.shape[:2]
                pts = [(int(l.x * fw2), int(l.y * fh2)) for l in lm]
                palm_cx = int(lm[9].x * fw2)
                palm_cy = int(lm[9].y * fh2)

                # Trail
                if trail_on:
                    _trail.append((palm_cx, palm_cy))
                    draw_trail(frame, color)

                # Glow skeleton
                draw_hand_glow(frame, pts, color, enabled=glow_on)

                # Scan ring
                radius = int(_hand_scale(lm) * fw2 * 1.4)
                radius = max(40, min(180, radius))
                draw_scan_ring(frame, palm_cx, palm_cy, radius, color, confidence)

                # Particules update
                if particles:
                    ps.update_and_draw(frame, dt)

                # ── MODE POINTER : contrôle souris ──────────────────────────
                if mode == MODE_POINTER:
                    pointer_ctrl.move(lm)
                    pointer_ctrl.process(lm, confirmed)
                    draw_pointer_overlay(frame, pts, pointer_ctrl)
                    sx, sy = pointer_ctrl.screen_pos
                    overlay.update(sx, sy, pointer_ctrl.action,
                                   pointer_ctrl.overlay_state, pointer_ctrl.press_ratio)
                    if pointer_ctrl.action:
                        state["last_action"] = pointer_ctrl.action
                    last_confirmed = confirmed
                    # G_MODE (rock) sort du mode pointeur comme les autres
                    if (confirmed == G_MODE
                            and confirmed != last_exec_gesture
                            and now - last_action_t >= cooldown):
                        state["mode"]          = (mode + 1) % 4
                        state["manual_switch"] = now
                        new_name               = MODE_NAMES[state["mode"]]
                        log.info(f"[MODE] → {new_name}")
                        state["last_action"] = f"Mode {new_name}"
                        speak(new_name)
                        tray.update(state["mode"])
                        play_beep(880, 60)
                        play_beep(1100, 60)
                        last_action_t     = now
                        last_exec_gesture = confirmed

                # ── Hold ────────────────────────────────────────────────────
                elif confirmed != G_NONE and confirmed == last_confirmed:
                    if hold_start == 0.0:
                        hold_start = now
                    elapsed   = now - hold_start
                    hold_prog = elapsed / hold_dur
                    if elapsed >= hold_dur and not hold_fired:
                        hold_fired = True
                        desc = execute_secondary(confirmed, mode, cfg, state)
                        if desc:
                            log.info(f"[HOLD] {confirmed} → {desc}")
                            state["last_action"] = f"⟳ {desc}"
                            notify("Jarvis", desc, cfg)
                            if cfg.get("tts_enabled", True): speak(desc)
                            play_beep(theme["beep"][0] // 2, 200)
                            if particles:
                                for _ in range(3):
                                    ps.burst(palm_cx, palm_cy, color, 15)
                        last_action_t = now
                else:
                    if confirmed != last_confirmed:
                        hold_start = 0.0
                        hold_fired = False

                # ── Primary action ───────────────────────────────────────────
                if (mode != MODE_POINTER
                        and confirmed != G_NONE
                        and confirmed != last_exec_gesture
                        and now - last_action_t >= cooldown):

                    if confirmed == G_MODE:
                        state["mode"]          = (mode + 1) % 4
                        state["manual_switch"] = now
                        new_name               = MODE_NAMES[state["mode"]]
                        log.info(f"[MODE] → {new_name}")
                        state["last_action"] = f"Mode {new_name}"
                        notify("Jarvis", f"Mode {new_name}", cfg)
                        if cfg.get("tts_enabled", True): speak(new_name)
                        tray.update(state["mode"])
                        play_beep(880, 60)
                        play_beep(1100, 60)
                    else:
                        desc = execute_primary(confirmed, mode, cfg, state)
                        if desc:
                            log.info(f"[{MODE_NAMES[mode]}] {confirmed} → {desc}")
                            state["last_action"] = desc
                            notify("Jarvis", desc, cfg)
                            if cfg.get("tts_enabled", True): speak(desc)
                            b = theme["beep"]
                            play_beep(b[0], b[1])
                            record_gesture(confirmed)
                            if particles:
                                ps.burst(palm_cx, palm_cy, color, 40)

                    last_action_t     = now
                    last_exec_gesture = confirmed

                last_confirmed = confirmed

            else:
                # Pas de main
                if last_confirmed != G_NONE:
                    gf.reset()
                    hold_start        = 0.0
                    hold_fired        = False
                    last_exec_gesture = G_NONE
                    _trail.clear()
                last_confirmed = G_NONE
                confirmed  = G_NONE
                dominant   = G_NONE
                confidence = 0.0
                if particles:
                    ps.update_and_draw(frame, dt)

            # Coins HUD
            draw_corners(frame, color, size=28, thickness=2)

            # OSD complet
            if preview:
                draw_osd(frame, state, confirmed, dominant, confidence, hold_prog, fps)
                cv2.imshow("Jarvis Elite", frame)
                key = cv2.waitKey(1) & 0xFF

                if key in (ord("q"), ord("Q")):
                    state["running"] = False
                elif key in (ord("m"), ord("M")):
                    state["mode"] = (state["mode"] + 1) % 4
                    state["manual_switch"] = now
                    tray.update(state["mode"])
                    log.info(f"[M] Mode → {MODE_NAMES[state['mode']]}")
                elif key in (ord("s"), ord("S")):
                    if cfg.get("tts_enabled", True):
                        speak(f"Mode {MODE_NAMES[state['mode']]}. {state.get('last_action','Prêt.')}")
                elif key == ord("1"):
                    state["mode"] = MODE_MEDIA;   state["manual_switch"] = now; tray.update(MODE_MEDIA)
                elif key == ord("2"):
                    state["mode"] = MODE_PC;      state["manual_switch"] = now; tray.update(MODE_PC)
                elif key == ord("3"):
                    state["mode"] = MODE_IA;      state["manual_switch"] = now; tray.update(MODE_IA)
                elif key == ord("4"):
                    state["mode"] = MODE_POINTER; state["manual_switch"] = now; tray.update(MODE_POINTER)
                    pointer_ctrl.frozen = False
                    log.info("[4] Mode POINTER activé")
                elif key in (ord("g"), ord("G")):
                    glow_on = not glow_on
                    log.info(f"Glow: {'ON' if glow_on else 'OFF'}")
                elif key in (ord("p"), ord("P")):
                    particles = not particles
                    log.info(f"Particules: {'ON' if particles else 'OFF'}")

    finally:
        speak("Jarvis hors ligne")
        cap.release()
        if preview:
            cv2.destroyAllWindows()
        detector.close()
        log.info("Jarvis Elite arrêté. À bientôt !")


if __name__ == "__main__":
    main()
