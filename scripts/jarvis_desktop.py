"""
Jarvis Desktop — detection gestuelle sans navigateur
Deps: pip install mediapipe opencv-python
"""

import cv2
import mediapipe as mp
import ctypes
import time
import sys
import os
import threading
import urllib.request
import json

# ── Modele MediaPipe (telecharge automatiquement au premier lancement) ─────────
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand_landmarker.task')
MODEL_URL  = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'

if not os.path.exists(MODEL_PATH):
    print('  Téléchargement du modèle MediaPipe (~25 Mo)...')
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print('  Modèle prêt.\n')
    except Exception as e:
        print(f'  Erreur téléchargement: {e}')
        sys.exit(1)

# ── MediaPipe Tasks (nouvelle API, mediapipe >= 0.10) ─────────────────────────
HandLandmarker        = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode

_detector_opts = HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=2,
    min_hand_detection_confidence=0.65,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ── Dessin de la main via OpenCV (sans mp.solutions.drawing_utils) ────────────
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

def draw_hand(frame, landmarks, color):
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], color, 1)
    for p in pts:
        cv2.circle(frame, p, 3, color, -1)

# ── Touches systeme (ctypes, sans dependance externe) ─────────────────────────
_u32  = ctypes.windll.user32
KEYUP = 0x0002

def _press(vk): _u32.keybd_event(vk,0,0,0); _u32.keybd_event(vk,0,KEYUP,0)
def _hold(vk):  _u32.keybd_event(vk,0,0,0)
def _rel(vk):   _u32.keybd_event(vk,0,KEYUP,0)

VK_PLAY=0xB3; VK_NEXT=0xB0; VK_PREV=0xB1; VK_VOLU=0xAF; VK_VOLD=0xAE
VK_WIN=0x5B;  VK_ALT=0x12;  VK_TAB=0x09;  VK_F4=0x73;   VK_D=0x44

def alt_tab():
    _hold(VK_ALT); time.sleep(0.06); _press(VK_TAB); time.sleep(0.06); _rel(VK_ALT)

def alt_f4():
    _hold(VK_ALT); _press(VK_F4); _rel(VK_ALT)

def win_d():
    _hold(VK_WIN); _press(VK_D); _rel(VK_WIN)

def win_tab():
    _hold(VK_WIN); _press(VK_TAB); _rel(VK_WIN)

# ── Mapping geste → action ────────────────────────────────────────────────────
ACTIONS = {
    'MEDIA': {
        'STOP':     lambda: _press(VK_PLAY),   # paume  → pause/play
        'NAVIGATE': lambda: _press(VK_NEXT),   # index  → suivant
        'SELECT':   lambda: _press(VK_PREV),   # poing  → precedent
        'VALIDATE': lambda: _press(VK_VOLU),   # pouce  → volume +
        'SCROLL':   lambda: _press(VK_VOLD),   # 2 dgt  → volume -
    },
    'PC': {
        'STOP':     win_d,                     # paume  → bureau
        'NAVIGATE': alt_tab,                   # index  → Alt+Tab
        'SELECT':   alt_f4,                    # poing  → fermer
        'VALIDATE': lambda: _press(VK_WIN),    # pouce  → Demarrer
        'SCROLL':   win_tab,                   # 2 dgt  → vue taches
    },
}

ACTION_LABELS = {
    'MEDIA': {'STOP':'Pause/Play','NAVIGATE':'Suivant','SELECT':'Precedent','VALIDATE':'Vol+','SCROLL':'Vol-'},
    'PC':    {'STOP':'Bureau','NAVIGATE':'Alt+Tab','SELECT':'Fermer','VALIDATE':'Demarrer','SCROLL':'Vue taches'},
    'IA':    {'STOP':'Annuler','NAVIGATE':'Options','SELECT':'Resumer','VALIDATE':'Confirmer','SCROLL':'Idees'},
}

GESTURE_NAMES = {
    'STOP':'Paume','NAVIGATE':'Index','SELECT':'Poing',
    'VALIDATE':'Pouce','SCROLL':'2 doigts','MODE':'Rock',
}

# ── Mode IA → appel n8n ───────────────────────────────────────────────────────
def call_ia(gesture):
    def _do():
        try:
            payload = json.dumps({'gesture': gesture, 'mode': 'IA'}).encode()
            req = urllib.request.Request(
                'http://localhost:5678/webhook/jarvis',
                data=payload, headers={'Content-Type': 'application/json'}, method='POST',
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read()).get('response', '...')
                print(f"\n  Jarvis IA: {resp}\n  {'─'*50}")
        except Exception as e:
            print(f"  [IA] Erreur: {e}")
    threading.Thread(target=_do, daemon=True).start()

# ── Classification des gestes ─────────────────────────────────────────────────
def get_fingers(lm):
    return [
        abs(lm[4].x - lm[5].x) > 0.07,
        lm[8].y  < lm[6].y,
        lm[12].y < lm[10].y,
        lm[16].y < lm[14].y,
        lm[20].y < lm[18].y,
    ]

def classify(lm):
    th, ix, mi, ri, pi = get_fingers(lm)
    if ix and mi and ri and pi:                            return 'STOP'
    if not th and not ix and not mi and not ri and not pi: return 'SELECT'
    if ix and not mi and not ri and not pi:                return 'NAVIGATE'
    if ix and mi and not ri and not pi:                    return 'SCROLL'
    if th and not ix and not mi and not ri and not pi:     return 'VALIDATE'
    if ix and not mi and not ri and pi:                    return 'MODE'
    return None

# ── Couleurs HUD ──────────────────────────────────────────────────────────────
COLORS = {'MEDIA':(80,210,50), 'PC':(50,170,245), 'IA':(60,60,230)}
MODES  = ['MEDIA', 'PC', 'IA']

# ── Lancement ─────────────────────────────────────────────────────────────────
COOLDOWN = 1.5

mode_idx        = 0
current_gesture = None
last_trigger    = 0.0

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print('Erreur : impossible d\'ouvrir la camera.'); sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS,          30)

print('\n  ╔══════════════════════════════╗')
print('  ║     JARVIS DESKTOP ACTIF     ║')
print('  ╚══════════════════════════════╝')
print('  Rock  → changer de mode')
print('  [ Q ] → quitter\n')

with HandLandmarker.create_from_options(_detector_opts) as detector:
    while True:
        ret, frame = cap.read()
        if not ret: break

        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ts_ms  = int(time.monotonic() * 1000)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect_for_video(mp_img, ts_ms)

        mode  = MODES[mode_idx]
        color = COLORS[mode]
        now   = time.time()
        detected = None

        if result.hand_landmarks:
            for i, hand_lm in enumerate(result.hand_landmarks):
                hcol = color if i == 0 else (180, 100, 240)
                draw_hand(frame, hand_lm, hcol)
                cx = int(hand_lm[8].x * frame.shape[1])
                cy = int(hand_lm[8].y * frame.shape[0])
                k  = classify(hand_lm)
                cv2.circle(frame, (cx, cy), 12 if k == 'NAVIGATE' else 5, hcol, 2)
                if k == 'NAVIGATE':
                    cv2.line(frame, (cx-18, cy), (cx+18, cy), hcol, 1)
                    cv2.line(frame, (cx, cy-18), (cx, cy+18), hcol, 1)

            detected = classify(result.hand_landmarks[0])

        if detected and detected != current_gesture:
            current_gesture = detected
            if detected == 'MODE':
                mode_idx = (mode_idx + 1) % len(MODES)
                print(f'  ── Mode {MODES[mode_idx]} ──')
            elif now - last_trigger > COOLDOWN:
                if mode == 'IA':
                    call_ia(detected)
                else:
                    fn = ACTIONS.get(mode, {}).get(detected)
                    if fn: fn()
                last_trigger = now
                lbl   = ACTION_LABELS.get(mode, {}).get(detected, detected)
                gname = GESTURE_NAMES.get(detected, detected)
                print(f'  [{time.strftime("%H:%M:%S")}]  {mode:<6} {gname:<12} → {lbl}')
        elif not detected:
            current_gesture = None

        # HUD
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 52), (18, 18, 18), -1)
        cv2.putText(frame, f'MODE : {mode}', (12, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        if current_gesture and current_gesture != 'MODE':
            lbl = ACTION_LABELS.get(mode, {}).get(current_gesture, '')
            cv2.putText(frame, lbl, (frame.shape[1] - 210, 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        cv2.imshow('Jarvis', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
