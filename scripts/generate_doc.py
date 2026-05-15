"""
Génère le document Word de récap du projet Jarvis + Stack IA
Dépendance : pip install python-docx Pillow
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime, os

doc = Document()

# ── Styles globaux ────────────────────────────────────────────────────────────
style_normal = doc.styles['Normal']
style_normal.font.name = 'Calibri'
style_normal.font.size = Pt(11)

def set_col_width(table, col_idx, width_cm):
    for row in table.rows:
        row.cells[col_idx].width = Cm(width_cm)

def heading(text, level=1, color=None):
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = h.runs[0] if h.runs else h.add_run(text)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return h

def para(text, bold=False, italic=False, size=11, color=None, align=None):
    p = doc.add_paragraph()
    if align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor(*color)
    return p

def code_block(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(text)
    r.font.name = 'Courier New'
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x1e, 0x1e, 0x2e)
    # Background gris clair via shading
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F0F0F0')
    pPr.append(shd)
    return p

def add_table(headers, rows, col_widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    hdr_row = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr_row[i].text = h
        hdr_row[i].paragraphs[0].runs[0].bold = True
        hdr_row[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tc = hdr_row[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), '2E4057')
        tcPr.append(shd)
    for row in rows:
        r = t.add_row().cells
        for i, val in enumerate(row):
            r[i].text = val
    if col_widths:
        for i, w in enumerate(col_widths):
            set_col_width(t, i, w)
    doc.add_paragraph()
    return t

def divider():
    doc.add_paragraph('─' * 80).paragraph_format.space_after = Pt(2)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE DE TITRE
# ═══════════════════════════════════════════════════════════════════════════════
doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('JARVIS & STACK IA — RAPPORT DE MODIFICATIONS')
r.bold = True
r.font.size = Pt(22)
r.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)

doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Self-Hosted AI Stack · Gesture Control System')
r.font.size = Pt(14)
r.font.color.rgb = RGBColor(0x55, 0x55, 0x99)

doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run(f'Généré le {datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")}')
r.font.size = Pt(10)
r.italic = True
r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

doc.add_paragraph()
divider()
doc.add_paragraph()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. RÉSUMÉ EXÉCUTIF
# ═══════════════════════════════════════════════════════════════════════════════
heading('1. Résumé exécutif', 1, (0x1a, 0x1a, 0x2e))
para(
    "Ce document récapitule l'ensemble des modifications apportées au projet "
    "self-hosted AI stack situé dans C:\\Users\\antho\\Documents\\mon-ia. "
    "Le projet comprend deux axes principaux : (1) Jarvis, un système de contrôle "
    "gestuel par caméra, et (2) une stack IA complète avec Ollama, n8n, Qdrant, "
    "SearXNG et LiteLLM."
)
doc.add_paragraph()
para("Session initiale — Jarvis v1/v2 + Stack IA :", bold=True)
items_v2 = [
    "Création du système de contrôle gestuel Jarvis (HTML + Desktop)",
    "Mise en place du mode 2 mains avec détection MediaPipe",
    "Curseur main libre sur le flux caméra",
    "Système de modes (MEDIA / PC / IA) avec geste Rock pour cycler",
    "Agent PowerShell (port 9999) pour le contrôle Media et PC sans navigateur",
    "Script Python autonome jarvis/desktop.py (v2, 750+ lignes)",
    "Pipeline RAG n8n complet avec mémoire Qdrant + recherche SearXNG",
    "Refonte de la logique geste → action pour plus d'intuitivité",
    "Détection de geste maintenu (hold 2s = action secondaire)",
    "Auto-détection du mode selon l'application active",
    "Vision IA : capture d'écran + analyse Ollama llava",
    "System tray icon dynamique (pystray)",
    "Notifications Windows (win10toast)",
    "Réorganisation complète du dossier projet",
]
for item in items_v2:
    p = doc.add_paragraph(style='List Bullet')
    p.add_run(item)

doc.add_paragraph()
para("Session mai 2026 — Authentik SSO + Jarvis v3 Elite Edition :", bold=True)
items_v3 = [
    "Déploiement Authentik SSO avec Caddy forward_auth (outpost embedded)",
    "Débogage complet du flux OAuth2 / état cookie (mismatched session ID)",
    "Ajout Langfuse (observabilité LLM), Grafana + Prometheus (monitoring)",
    "Jarvis v3 Elite Edition : refonte visuelle totale avec effets neon OpenCV",
    "Système de particules 2D (burst au changement de geste/mode)",
    "Squelette main avec halo neon (GaussianBlur numpy)",
    "Anneau de scan animé avec arc rotatif (confidence visuelle)",
    "Vignette plein-écran par broadcasting numpy",
    "Trail de points — historique de position de l'index",
    "HUD avancé : watermark JARVIS, brackets d'angle, historique gestes, barre cooldown",
    "Thèmes couleurs par mode (vert MEDIA / bleu PC / violet IA)",
    "TTS async pyttsx3 (sélection voix française, file non-bloquante)",
    "Feedback audio winsound.Beep par geste et par mode",
    "Raccourcis clavier étendus : G (glow), P (particules), S (speak), 1/2/3 (modes directs)",
    "Intégration IA enrichie en mode IA (screenshot + contexte fenêtre active)",
]
for item in items_v3:
    p = doc.add_paragraph(style='List Bullet')
    p.add_run(item)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. STACK IA — SERVICES
# ═══════════════════════════════════════════════════════════════════════════════
heading('2. Stack IA self-hosted', 1, (0x1a, 0x1a, 0x2e))
para(
    "Le projet tourne entièrement via Docker Compose. Voici les services déployés :"
)
doc.add_paragraph()

add_table(
    ['Service', 'Port local', 'Domaine HTTPS', 'Rôle'],
    [
        ['Open WebUI',  ':8080',  'webui.local',      'Interface utilisateur pour Ollama'],
        ['LiteLLM',     ':4000',  'litellm.local',    'Proxy unifié pour les LLMs'],
        ['SearXNG',     ':8888',  'searxng.local',    'Moteur de recherche web privé'],
        ['Qdrant',      ':6333',  'qdrant.local',     'Base vectorielle pour la mémoire IA'],
        ['n8n',         ':5678',  'n8n.local',        'Orchestration de workflows IA'],
        ['Langfuse',    ':3000',  'langfuse.local',   'Observabilité & traces LLM'],
        ['Grafana',     ':3001',  'grafana.local',    'Dashboards monitoring'],
        ['Prometheus',  ':9090',  'prometheus.local', 'Collecte métriques Docker/LiteLLM'],
        ['Authentik',   ':9000',  'authentik.local',  'SSO — portail d\'authentification'],
        ['Caddy',       ':80/:443', '—',              'Reverse proxy HTTPS (TLS auto .local)'],
    ],
    col_widths=[3, 2.5, 3.5, 7]
)

heading('Architecture des services', 2)
code_block(
    "Navigateur / Jarvis Desktop\n"
    "         ↓\n"
    "    Caddy :443 (TLS .local)\n"
    "         ↓\n"
    "   ┌─────────────────────────────────────────────────┐\n"
    "   │  Open WebUI (:8080)   LiteLLM (:4000)          │\n"
    "   │  n8n (:5678) ─────→ Qdrant (:6333)             │\n"
    "   │  SearXNG (:8888) ──→ Internet                   │\n"
    "   │  Langfuse (:3000)    Grafana (:3001)            │\n"
    "   │  Prometheus (:9090)  Authentik (:9000)          │\n"
    "   │  Ollama (:11434) ─── host machine               │\n"
    "   └─────────────────────────────────────────────────┘\n"
    "\n"
    "LiteLLM → Langfuse (traces) + Prometheus (métriques)\n"
    "Authentik → SSO optionnel (outpost embedded Caddy forward_auth)"
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. STRUCTURE DU PROJET
# ═══════════════════════════════════════════════════════════════════════════════
heading('3. Restructuration du projet', 1, (0x1a, 0x1a, 0x2e))
para("Avant la session, les fichiers Jarvis étaient éparpillés à la racine et dans scripts/. "
     "La nouvelle organisation regroupe tout par domaine fonctionnel.")

doc.add_paragraph()
heading('Avant', 2)
code_block(
    "mon-ia/\n"
    "├── docker-compose.yaml\n"
    "├── jarvis_gesture_control.html     ← racine\n"
    "├── jarvis_n8n_workflow.json        ← racine\n"
    "├── scripts/\n"
    "│   ├── start.py / stop.py / restart.py\n"
    "│   ├── jarvis_desktop.py           ← scripts/\n"
    "│   ├── jarvis_agent.ps1            ← scripts/\n"
    "│   └── hand_landmarker.task        ← scripts/\n"
    "├── caddy/ certs/ n8n/ searxng/ ...\n"
    "└── tailscale-setup-1.96.3.exe"
)

heading('Après', 2)
code_block(
    "mon-ia/\n"
    "├── docker-compose.yaml\n"
    "│\n"
    "├── jarvis/                         ← NOUVEAU : tout Jarvis\n"
    "│   ├── desktop.py                  ← v2, 750+ lignes\n"
    "│   ├── agent.ps1                   ← serveur HTTP port 9999\n"
    "│   ├── launch.ps1                  ← lance tout d'un coup\n"
    "│   ├── web.html                    ← interface navigateur\n"
    "│   ├── config.json                 ← configuration centralisée\n"
    "│   └── models/\n"
    "│       └── hand_landmarker.task    ← auto-téléchargé\n"
    "│\n"
    "├── n8n/\n"
    "│   ├── data/                       ← volume Docker (inchangé)\n"
    "│   └── workflows/                  ← NOUVEAU\n"
    "│       ├── jarvis_ia.json          ← workflow simple\n"
    "│       └── jarvis_ia_complete.json ← pipeline RAG complet\n"
    "│\n"
    "├── scripts/                        ← uniquement scripts Docker\n"
    "│   ├── start.py\n"
    "│   ├── stop.py\n"
    "│   └── restart.py\n"
    "│\n"
    "└── caddy/ certs/ litellm/ searxng/ qdrant/ open-webui/"
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. JARVIS — SYSTÈME DE CONTRÔLE GESTUEL
# ═══════════════════════════════════════════════════════════════════════════════
heading('4. Jarvis — Système de contrôle gestuel', 1, (0x1a, 0x1a, 0x2e))
para(
    "Jarvis est un système de reconnaissance de gestes de la main en temps réel "
    "qui permet de contrôler le PC, les médias et l'IA locale sans toucher au clavier. "
    "Il existe en deux versions : une interface web (navigateur) et une application desktop autonome."
)

heading('4.1 Interface Web (jarvis/web.html)', 2)
para("Fonctionne dans le navigateur via Open WebUI. Utilise MediaPipe CDN pour la détection.")
doc.add_paragraph()
add_table(
    ['Fonctionnalité', 'Détail'],
    [
        ['Flux caméra', 'Détection temps réel via MediaPipe Hands'],
        ['2 mains simultanées', 'Main 1 (bleu) déclenche les actions, Main 2 (violet) affichée'],
        ['Curseur main libre', 'Cercle + viseur sur l\'index (lm[8]) dans le canvas'],
        ['3 modes', 'MEDIA / PC / IA — chip coloré en haut à droite'],
        ['Bibliothèque de gestes', 'Labels mis à jour dynamiquement selon le mode actif'],
        ['Réponse IA', 'Panneau rouge affiché en mode IA avec réponse Ollama'],
        ['Support 2 mains', 'Panneau MAIN 1 (bleu) + MAIN 2 (violet) avec état des doigts'],
    ],
    col_widths=[5, 11]
)

heading('4.2 Application Desktop (jarvis/desktop.py)', 2)
para("Script Python autonome — aucun navigateur requis. S'exécute en arrière-plan.")
doc.add_paragraph()
add_table(
    ['Fonctionnalité', 'Détail'],
    [
        ['MediaPipe Tasks API', 'Nouvelle API (>= 0.10), sans mp.solutions deprecated'],
        ['Modèle auto-téléchargé', 'hand_landmarker.task (~25 Mo) téléchargé au 1er lancement'],
        ['System tray', 'Icône colorée (pystray) — vert/bleu/rouge selon le mode'],
        ['Geste maintenu (hold)', 'Tenir 2s = action secondaire + barre de progression HUD'],
        ['Auto-mode', 'Détecte l\'app active toutes les 3s (Spotify → MEDIA, VS Code → PC)'],
        ['Vision IA', 'NAVIGATE en mode IA → screenshot + analyse Ollama llava'],
        ['Notifications', 'Toast Windows via win10toast (optionnel)'],
        ['Touches clavier', '[ Q ] quitter, [ M ] changer de mode'],
        ['Dessin main OpenCV', 'Sans mp.solutions.drawing_utils (supprimé dans nouvelle API)'],
        ['Config JSON', 'Tous les paramètres dans jarvis/config.json'],
    ],
    col_widths=[5, 11]
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. SYSTÈME DE GESTES
# ═══════════════════════════════════════════════════════════════════════════════
heading('5. Système de gestes', 1, (0x1a, 0x1a, 0x2e))
para(
    "6 gestes sont détectés, chacun ayant une signification universelle "
    "appliquée de manière cohérente dans tous les modes. Le geste Rock est réservé au changement de mode."
)
doc.add_paragraph()
add_table(
    ['Geste', 'Symbole', 'Mode MEDIA', 'Mode PC', 'Mode IA'],
    [
        ['Paume ouverte',  '✋', 'Pause / Play',      'Bureau (Win+D)',    'Annuler'],
        ['Index levé',     '☝️', 'Piste suivante →',  'Alt+Tab',          'Screenshot Ollama'],
        ['Poing fermé',    '✊', '← Piste précédente','Fermer (Alt+F4)',   'Résumer'],
        ['Pouce levé',     '👍', 'Volume +',           'Menu Démarrer',    'Confirmer'],
        ['2 doigts (V)',   '✌️', 'Volume —',           'Vue tâches Win+Tab','Nouvelles idées'],
        ['Signe Rock',     '🤘', 'Changer mode →',     'Changer mode →',   'Changer mode →'],
    ],
    col_widths=[3.5, 2, 3.5, 3.5, 3.5]
)

heading('Actions secondaires (geste maintenu 2s)', 2)
add_table(
    ['Geste maintenu', 'Mode MEDIA', 'Mode PC'],
    [
        ['Paume (STOP)', 'Mute / Unmute', 'Verrouillage écran (Win+L)'],
        ['Autres gestes', 'Répète l\'action primaire', 'Répète l\'action primaire'],
    ],
    col_widths=[5, 6, 6]
)

heading('Logique de détection (classification)', 2)
code_block(
    "def classify(lm):  # lm = liste de 21 landmarks MediaPipe\n"
    "    th, ix, mi, ri, pi = get_fingers(lm)  # pouce, index, majeur, annulaire, auriculaire\n"
    "    if ix and mi and ri and pi:             → STOP    (paume)\n"
    "    if not th and not ix and not mi...:     → SELECT  (poing)\n"
    "    if ix and not mi and not ri and not pi: → NAVIGATE (index)\n"
    "    if ix and mi and not ri and not pi:     → SCROLL  (2 doigts)\n"
    "    if th and not ix and not mi...:         → VALIDATE (pouce)\n"
    "    if ix and not mi and not ri and pi:     → MODE    (rock)\n"
    "\n"
    "# Pouce : détecté si abs(lm[4].x - lm[5].x) > 0.07 (écarté latéralement)\n"
    "# Autres doigts : levés si tip.y < pip.y (bout du doigt plus haut que phalange)"
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 6. AGENT POWERSHELL
# ═══════════════════════════════════════════════════════════════════════════════
heading('6. Agent PowerShell (jarvis/agent.ps1)', 1, (0x1a, 0x1a, 0x2e))
para(
    "Serveur HTTP léger sur localhost:9999. Reçoit les commandes depuis le navigateur "
    "ou desktop.py et exécute les touches système Windows via keybd_event (ctypes)."
)
doc.add_paragraph()
add_table(
    ['Aspect', 'Détail'],
    [
        ['Port',          'localhost:9999'],
        ['Endpoint',      'POST /gesture  →  {mode, gesture}'],
        ['CORS',          'Access-Control-Allow-Origin: * (appels depuis navigateur autorisés)'],
        ['Touches media', 'keybd_event VK_MEDIA_PLAY_PAUSE (0xB3), VK_NEXT, VK_PREV, VK_VOLUME_*'],
        ['Touches PC',    'Win+D, Alt+Tab, Alt+F4, Win, Win+Tab via keybd_event'],
        ['Encodage',      'Accents normalisés : É → E avant le switch'],
        ['Logs console',  '[HH:MM:SS]  MODE  ·  GESTE  affiché en cyan'],
    ],
    col_widths=[4, 12]
)

heading('Commande de lancement', 2)
code_block("powershell -ExecutionPolicy Bypass -File jarvis\\agent.ps1")

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 7. PIPELINE RAG — WORKFLOW N8N
# ═══════════════════════════════════════════════════════════════════════════════
heading('7. Pipeline RAG — Workflow n8n', 1, (0x1a, 0x1a, 0x2e))
para(
    "Le fichier n8n/workflows/jarvis_ia_complete.json implémente un pipeline RAG "
    "(Retrieval-Augmented Generation) complet. Il connecte n8n, Qdrant, SearXNG et Ollama "
    "pour fournir des réponses contextualisées aux gestes en mode IA."
)

heading('Flux du pipeline', 2)
code_block(
    "Geste IA détecté\n"
    "     ↓\n"
    "  Webhook n8n POST /webhook/jarvis\n"
    "     ↓\n"
    "  [Code] Mapper geste → prompt\n"
    "     ↓\n"
    "  [Code] Embedding du prompt via Ollama (nomic-embed-text)\n"
    "     ↓\n"
    "  [Code] Recherche Qdrant (mémoire des échanges passés, score > 0.6)\n"
    "     ↓\n"
    "  [Code] Si geste = NAVIGATE → recherche SearXNG (actualités web)\n"
    "     ↓\n"
    "  [Code] Appel Ollama /api/chat avec :\n"
    "         • System prompt Jarvis\n"
    "         • Contexte mémoire Qdrant\n"
    "         • Résultats web SearXNG (si NAVIGATE)\n"
    "         • Prompt utilisateur\n"
    "     ↓\n"
    "  [Code] Stockage Q+R dans Qdrant (vecteur + payload)\n"
    "     ↓\n"
    "  Réponse JSON → desktop.py → notification + log"
)

doc.add_paragraph()
add_table(
    ['Geste IA', 'Prompt envoyé à Ollama'],
    [
        ['STOP    (paume)',   'Donne-moi un point de situation rapide.'],
        ['NAVIGATE (index)',  'Recherche web + quelles options ai-je disponibles ?'],
        ['SELECT  (poing)',   'Résume notre conversation et la situation actuelle.'],
        ['VALIDATE (pouce)', 'Confirme et valide la dernière action effectuée.'],
        ['SCROLL  (2 dgt)',  'Propose-moi 3 nouvelles idées créatives à explorer.'],
    ],
    col_widths=[4, 12]
)

heading('Mémoire Qdrant', 2)
para("Collection : jarvis_memory — créée automatiquement au premier appel.")
add_table(
    ['Champ', 'Type', 'Description'],
    [
        ['vector',    '768 floats', 'Embedding nomic-embed-text du prompt+réponse'],
        ['question',  'string',     'Prompt envoyé à Ollama'],
        ['answer',    'string',     'Réponse d\'Ollama'],
        ['gesture',   'string',     'Geste qui a déclenché la requête'],
        ['timestamp', 'ISO 8601',   'Date/heure de l\'échange'],
    ],
    col_widths=[3, 3, 10]
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 8. CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
heading('8. Configuration (jarvis/config.json)', 1, (0x1a, 0x1a, 0x2e))
code_block(
    '{\n'
    '  "cooldown":       1.5,          // délai min entre deux déclenchements (secondes)\n'
    '  "hold_duration":  2.0,          // durée maintien geste pour action secondaire\n'
    '  "notifications_enabled": true,  // notifications Windows toast\n'
    '  "camera_index":   0,            // index caméra (0 = webcam principale)\n'
    '  "preview_window": true,         // afficher la fenêtre caméra OpenCV\n'
    '  "auto_mode":      true,         // auto-switcher mode selon app active\n'
    '  "n8n_url":        "http://localhost:5678",\n'
    '  "ollama_url":     "http://localhost:11434",\n'
    '  "default_model":  "llama3.2",   // modèle Ollama pour le mode IA\n'
    '  "vision_model":   "llava",      // modèle vision pour screenshot\n'
    '  "embed_model":    "nomic-embed-text",  // modèle embeddings Qdrant\n'
    '  "default_mode":   0             // 0=MEDIA, 1=PC, 2=IA\n'
    '}'
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 9. DÉPENDANCES
# ═══════════════════════════════════════════════════════════════════════════════
heading('9. Dépendances Python', 1, (0x1a, 0x1a, 0x2e))
add_table(
    ['Package', 'Version', 'Rôle', 'Requis ?'],
    [
        ['mediapipe',    '>= 0.10', 'Détection gestes (Tasks API)',     'OUI'],
        ['opencv-python','latest',  'Capture caméra + dessin HUD',      'OUI'],
        ['requests',     'latest',  'Appels HTTP n8n / Ollama',         'OUI'],
        ['pystray',      'latest',  'Icône system tray',                'Optionnel'],
        ['Pillow',       'latest',  'Screenshot pour vision IA',        'Optionnel'],
        ['win10toast',   'latest',  'Notifications Windows',            'Optionnel'],
        ['python-docx',  'latest',  'Génération ce document Word',      'Optionnel'],
    ],
    col_widths=[4, 2.5, 7, 2.5]
)

para("Ajout mai 2026 :", bold=True)
add_table(
    ['Package', 'Version', 'Rôle', 'Requis ?'],
    [
        ['pyttsx3', 'latest', 'TTS offline async (voix française Windows)', 'Optionnel'],
        ['comtypes', '1.4.16', 'Dépendance pyttsx3 (Windows COM)', 'Auto'],
    ],
    col_widths=[4, 2.5, 7, 2.5]
)

heading('Commande d\'installation', 2)
code_block(
    "# Requis\n"
    "pip install mediapipe>=0.10 opencv-python requests\n\n"
    "# Optionnel (recommandé)\n"
    "pip install pystray Pillow win10toast python-docx\n\n"
    "# Ajouté session mai 2026\n"
    "pip install pyttsx3   # TTS async non-bloquant\n\n"
    "# Modèles Ollama\n"
    "ollama pull llama3.2\n"
    "ollama pull llava\n"
    "ollama pull nomic-embed-text"
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 10. DÉMARRAGE
# ═══════════════════════════════════════════════════════════════════════════════
heading('10. Comment démarrer', 1, (0x1a, 0x1a, 0x2e))

heading('Option 1 — Tout en une commande (recommandé)', 2)
code_block(
    "cd C:\\Users\\antho\\Documents\\mon-ia\n"
    "powershell -ExecutionPolicy Bypass -File jarvis\\launch.ps1"
)
para("Le launcher vérifie Python, les dépendances, démarre l'agent PS1 en arrière-plan "
     "puis lance desktop.py. Quand vous appuyez sur Q dans la fenêtre caméra, l'agent est aussi arrêté.")

heading('Option 2 — Séparé', 2)
code_block(
    "# Terminal 1 — Agent HTTP (port 9999)\n"
    "powershell -ExecutionPolicy Bypass -File jarvis\\agent.ps1\n\n"
    "# Terminal 2 — Détection gestuelle\n"
    "python jarvis\\desktop.py"
)

heading('Importer le workflow n8n', 2)
p = doc.add_paragraph(style='List Number')
p.add_run('Aller sur ').bold = False
p.add_run('http://localhost:5678').bold = True
p = doc.add_paragraph(style='List Number')
p.add_run('Workflows → Import workflow')
p = doc.add_paragraph(style='List Number')
p.add_run('Sélectionner ').bold = False
p.add_run('n8n/workflows/jarvis_ia_complete.json').bold = True
p = doc.add_paragraph(style='List Number')
p.add_run('Activer le workflow (toggle en haut à droite)')

heading('Premier lancement', 2)
para("Au premier démarrage, desktop.py télécharge automatiquement le modèle "
     "hand_landmarker.task (~25 Mo) dans jarvis/models/. Les démarrages suivants sont instantanés.")

doc.add_paragraph()
divider()
doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Document généré automatiquement — Projet Jarvis & Stack IA Self-Hosted')
r.italic = True
r.font.size = Pt(9)
r.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 11. JARVIS v3 ELITE EDITION — REFONTE VISUELLE
# ═══════════════════════════════════════════════════════════════════════════════
heading('11. Jarvis v3 Elite Edition — Refonte visuelle (mai 2026)', 1, (0x1a, 0x1a, 0x2e))
para(
    "La version 3 de desktop.py est une refonte complète de l'interface caméra. "
    "Toutes les améliorations visuelles utilisent NumPy + OpenCV (aucune dépendance graphique externe). "
    "Le fichier compte désormais ~900 lignes."
)

heading('11.1 Thèmes couleurs par mode', 2)
para("Chaque mode possède sa propre palette appliquée à tous les éléments visuels :")
code_block(
    "THEMES = {\n"
    "  MODE_MEDIA: { primary:(0,255,128),   secondary:(0,160,80),   glow:(0,60,30),   beep:(880,80),  icon:'MEDIA' },\n"
    "  MODE_PC:    { primary:(80,180,255),  secondary:(40,100,200), glow:(10,30,80),  beep:(660,80),  icon:'PC'    },\n"
    "  MODE_IA:    { primary:(200,80,255),  secondary:(130,40,200), glow:(50,10,80),  beep:(1100,80), icon:'IA'    },\n"
    "}"
)

heading('11.2 Squelette main avec halo néon', 2)
para(
    "La main est dessinée en deux passes : (1) un layer numpy flou pour le glow, "
    "(2) les lignes/points principaux par-dessus. Les fingertips ont un rayon plus grand."
)
code_block(
    "def draw_hand_glow(frame, pts, color, enabled=True):\n"
    "    glow = np.zeros_like(frame, dtype=np.uint8)\n"
    "    for a, b in HAND_CONNECTIONS:\n"
    "        cv2.line(glow, pts[a], pts[b], color, 8)\n"
    "    for i,(x,y) in enumerate(pts):\n"
    "        cv2.circle(glow, (x,y), 12 if i in FINGERTIPS else 8, color, -1)\n"
    "    glow = cv2.GaussianBlur(glow, (31,31), 0)\n"
    "    frame[:] = cv2.add(frame, glow)  # addWeighted neon effect"
)

heading('11.3 Système de particules', 2)
para("Burst de 30 particules à chaque changement de geste ou de mode. Physique simple avec friction.")
code_block(
    "class Particle:\n"
    "    def __init__(self, x, y, color):\n"
    "        angle = random.uniform(0, math.tau)\n"
    "        speed = random.uniform(1.5, 5.0)\n"
    "        self.vx = math.cos(angle) * speed\n"
    "        self.vy = math.sin(angle) * speed\n"
    "        self.life = 1.0          # 0..1\n"
    "        self.r    = random.randint(2, 5)\n"
    "    def update(self, dt=0.033):\n"
    "        self.x += self.vx; self.y += self.vy\n"
    "        self.vx *= 0.92; self.vy *= 0.92   # friction\n"
    "        self.life -= dt * 2.5               # fade out"
)

heading('11.4 Anneau de scan animé', 2)
para("Cercle de confiance autour de la paume. Un arc de 90° tourne en continu pour indiquer la détection active.")
code_block(
    "_scan_angle = 0.0\n"
    "def draw_scan_ring(frame, cx, cy, radius, color, confidence):\n"
    "    global _scan_angle\n"
    "    _scan_angle = (_scan_angle + 3.5) % 360\n"
    "    # Cercle de base (faible opacité) + arc de 90° animé"
)

heading('11.5 Vignette plein-écran', 2)
para("Assombrit les bords de l'image à chaque frame via broadcasting NumPy (très rapide).")
code_block(
    "def apply_vignette(frame):\n"
    "    h, w = frame.shape[:2]\n"
    "    Y, X = np.ogrid[:h, :w]\n"
    "    dist = np.sqrt(((X-w//2)/(w//2))**2 + ((Y-h//2)/(h//2))**2)\n"
    "    vignette = np.clip(1.0 - dist * 0.55, 0.45, 1.0)\n"
    "    frame[:] = (frame * vignette[:,:,np.newaxis]).astype(np.uint8)"
)

heading('11.6 HUD avancé', 2)
add_table(
    ['Élément HUD', 'Description'],
    [
        ['Watermark JARVIS', 'Texte semi-transparent en bas à droite, taille 0.45'],
        ['Corner brackets',  '4 angles en L colorés selon le thème du mode actif'],
        ['Barre cooldown',   'Barre horizontale bas de frame — remplit entre deux déclenchements'],
        ['Historique gestes','5 derniers gestes affichés verticalement (fade-out progressif)'],
        ['Confidence ring',  'Arc de cercle proportionnel à la confiance de détection (0..1)'],
        ['Trail index',      'Traîne de 20 points derrière le bout de l\'index'],
        ['Anneau scan',      'Arc 90° rotatif autour de la paume — vert/bleu/violet selon mode'],
        ['Info panneau',     'Panneau latéral droit : mode actif, geste, action, raccourcis clavier'],
    ],
    col_widths=[4, 12]
)

heading('11.7 TTS et feedback audio', 2)
add_table(
    ['Mécanisme', 'Détail'],
    [
        ['pyttsx3 async', 'File de messages dans un thread daemon — non-bloquant pour la boucle caméra'],
        ['Voix française', 'Sélection automatique de la première voix contenant "fr" dans le nom'],
        ['Débit TTS', '180 mots/minute'],
        ['winsound.Beep', 'Bip à chaque action : fréquence et durée différentes par mode (880/660/1100 Hz)'],
        ['Feedback mode', 'Bip grave + TTS "Mode MEDIA / PC / IA activé" à chaque changement'],
    ],
    col_widths=[4, 12]
)

heading('11.8 Nouveaux raccourcis clavier', 2)
add_table(
    ['Touche', 'Action'],
    [
        ['Q', 'Quitter Jarvis'],
        ['M', 'Cycler le mode (MEDIA → PC → IA → MEDIA)'],
        ['1 / 2 / 3', 'Basculer directement en mode MEDIA / PC / IA'],
        ['S', 'TTS : parler l\'état actuel (mode + geste détecté)'],
        ['G', 'Activer / désactiver le halo néon (glow)'],
        ['P', 'Activer / désactiver le système de particules'],
    ],
    col_widths=[3, 13]
)

heading('11.9 Nouvelles clés config.json (v3)', 2)
code_block(
    '{\n'
    '  "tts_enabled":      true,   // activer / désactiver TTS pyttsx3\n'
    '  "particles_enabled": true,  // activer / désactiver burst particules\n'
    '  "glow_enabled":     true,   // activer / désactiver halo néon main\n'
    '  "trail_enabled":    true,   // activer / désactiver traîne index\n'
    '  "window_width":     960,    // largeur fenêtre OpenCV\n'
    '  "window_height":    560     // hauteur fenêtre OpenCV\n'
    '  // ... toutes les clés v2 inchangées\n'
    '}'
)

heading('11.10 Intégration IA enrichie (mode IA)', 2)
add_table(
    ['Geste', 'Comportement v3'],
    [
        ['STOP (paume)',    'Screenshot + prompt : "Décris en 2 phrases ce que tu vois et propose une action utile"'],
        ['NAVIGATE (index)', 'Interroge Ollama avec le titre de la fenêtre active comme contexte'],
        ['SELECT (poing)',  'Appel n8n webhook avec action SELECT'],
        ['VALIDATE (pouce)', 'Ollama : idées de productivité basées sur l\'écran actuel'],
        ['SCROLL (2 dgt)', 'Appel n8n webhook avec action SCROLL'],
    ],
    col_widths=[4, 12]
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════════
# 12. AUTHENTIK SSO — MISE EN PLACE ET DÉBOGAGE
# ═══════════════════════════════════════════════════════════════════════════════
heading('12. Authentik SSO — Configuration et débogage (mai 2026)', 1, (0x1a, 0x1a, 0x2e))
para(
    "Tentative de mise en place d'un SSO centralisé pour tous les services .local "
    "via Authentik + Caddy forward_auth (outpost embedded). "
    "Plusieurs bugs de session/cookie ont été identifiés et résolus. "
    "Le SSO Caddy a finalement été désactivé en raison d'une limitation fondamentale "
    "du partage de cookie entre sous-domaines .local."
)

heading('12.1 Architecture cible', 2)
code_block(
    "Navigateur → https://webui.local\n"
    "   ↓ Caddy forward_auth\n"
    "   → GET authentik:9000/outpost.goauthentik.io/auth/caddy\n"
    "   ← 200 (authentifié) : laisse passer\n"
    "   ← 302 (non authentifié) : Caddy intercepte\n"
    "   → redir navigateur vers https://authentik.local/outpost.goauthentik.io/start?rd=...\n"
    "   → Login Authentik → callback → cookie de session\n"
    "   → Retour vers https://webui.local (maintenant autorisé)"
)

heading('12.2 Bugs rencontrés et corrections', 2)
add_table(
    ['Bug', 'Cause', 'Correction'],
    [
        [
            'HTTP 400 — mismatched session ID / should:""',
            'handle_response ne catchait que status 401. L\'outpost embedded retourne 302 (pas 401) pour les non-authentifiés. Le navigateur suivait ce 302 vers /authorize sans passer par /start → pas de cookie d\'état → callback impossible.',
            'Matcher changé en : @goauthentik_proxy_response status 401 302'
        ],
        [
            'Cookie d\'état posé sur le mauvais domaine',
            'Redirect relative /outpost.goauthentik.io/start → navigateur appelle webui.local/start → cookie posé sur webui.local → callback sur authentik.local ne trouve pas le cookie.',
            'Redirect absolue : redir * https://authentik.local/outpost.goauthentik.io/start?rd={scheme}://{host}{uri}'
        ],
        [
            '"Not Found — Powered by authentik" sur /admin',
            'Cookie Domain = authentik.local → outpost ne gère que ce domaine, renvoie 404 pour webui.local/auth/caddy.',
            'Cookie Domain changé à local (sans sous-domaine) dans le Proxy Provider Authentik.'
        ],
        [
            'Chargement infini sur webui.local',
            'Session cookie posé sur authentik.local après login → non transmis avec les requêtes vers webui.local (domaines différents) → Caddy forward_auth toujours 302 → boucle infinie.',
            'Limitation fondamentale : impossible avec cookies browser standard. Solution : import sso retiré de tous les blocs Caddy. Services accessibles sans SSO.'
        ],
    ],
    col_widths=[4, 6, 6]
)

heading('12.3 Configuration Caddyfile finale', 2)
code_block(
    "(sso) {                                    # snippet non utilisé — conservé pour référence\n"
    "  forward_auth authentik:9000 {\n"
    "    uri /outpost.goauthentik.io/auth/caddy\n"
    "    copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email\n"
    "    @goauthentik_proxy_response status 401 302\n"
    "    handle_response @goauthentik_proxy_response {\n"
    "      redir * https://authentik.local/outpost.goauthentik.io/start?rd={scheme}://{host}{uri}\n"
    "    }\n"
    "  }\n"
    "}\n"
    "\n"
    "webui.local {\n"
    "  tls /certs/cert.pem /certs/key.pem\n"
    "  reverse_proxy open-webui:8080    # PAS d'import sso\n"
    "}\n"
    "# ... idem pour tous les services"
)

heading('12.4 Configuration Authentik requise', 2)
add_table(
    ['Paramètre', 'Valeur', 'Importance'],
    [
        ['Cookie Domain (Proxy Provider)', 'local', 'CRITIQUE — doit couvrir tous les .local'],
        ['Outpost config JSON — authentik_host', 'http://authentik:9000', 'Résolution interne Docker'],
        ['Outpost config JSON — authentik_host_browser', 'https://authentik.local', 'URL redirigée vers le navigateur'],
        ['Proxy Provider mode', 'Forward auth (single application)', 'Utilisé avec Caddy forward_auth'],
    ],
    col_widths=[5, 4, 7]
)

heading('12.5 Procédure de débogage Authentik', 2)
para("En cas de problème SSO, vérifier dans cet ordre :")
steps = [
    "Tester en navigation privée (évite les cookies corrompus en cache)",
    "Vérifier Caddyfile : handle_response avec status 401 302 et redirect absolu vers authentik.local",
    "Vérifier Authentik Provider : Cookie Domain = local (sans point ni sous-domaine)",
    "Vérifier Outpost config JSON : authentik_host_browser = https://authentik.local",
    "Vérifier logs Caddy : docker compose logs caddy --tail=50",
    "Vérifier logs Authentik : docker compose logs authentik --tail=50",
]
for i, step in enumerate(steps, 1):
    p = doc.add_paragraph(style='List Number')
    p.add_run(step)

heading('12.6 État final — mai 2026', 2)
para(
    "Authentik tourne sur https://authentik.local et est accessible. "
    "Le SSO Caddy (forward_auth) est désactivé pour les services car le partage de session "
    "cookie entre sous-domaines .local n'est pas supporté nativement sans reverse-proxy "
    "SSO-aware (ex : Traefik + ForwardAuth middleware + cookie shared domain). "
    "Les services restent accessibles en HTTPS sans authentification gate. "
    "Authentik reste disponible pour une future configuration OAuth2/OIDC native "
    "dans Open WebUI ou n8n."
)

doc.add_page_break()

# ── Sauvegarde ────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Jarvis_Recap.docx')
out = os.path.normpath(out)
try:
    doc.save(out)
    print(f"Document genere : {out}")
except PermissionError:
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    alt = out.replace('Jarvis_Recap.docx', f'Jarvis_Recap_{ts}.docx')
    doc.save(alt)
    print(f"Document genere (fichier principal verrouille) : {alt}")
