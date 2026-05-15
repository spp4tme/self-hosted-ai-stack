"""
Jarvis — Ingestion de documents dans Qdrant (RAG)
Usage : python scripts/ingest_docs.py [--reset]

Formats supportés : .txt .md .pdf .docx
Dossier source    : docs/
Collection Qdrant : jarvis_docs
Modèle embeddings : nomic-embed-text (via Ollama)
"""

import os, sys, json, hashlib, time, argparse
import urllib.request, urllib.error
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent.parent
DOCS_DIR    = BASE / "docs"
STATE_FILE  = DOCS_DIR / ".ingested.json"
QDRANT      = "http://localhost:6333"
OLLAMA      = "http://localhost:11434"
COLLECTION  = "jarvis_docs"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE  = 1200   # caractères par chunk
CHUNK_OVERLAP = 150  # chevauchement

# ── Helpers HTTP ──────────────────────────────────────────────────────────────
def _http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req  = urllib.request.Request(url, data=data, method=method,
                                   headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode()[:200]}")

def qdrant_get(path):
    req = urllib.request.Request(f"{QDRANT}{path}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# ── Qdrant init ───────────────────────────────────────────────────────────────
def ensure_collection(reset=False):
    try:
        info = qdrant_get(f"/collections/{COLLECTION}")
        if reset:
            _http("DELETE", f"{QDRANT}/collections/{COLLECTION}")
            print(f"  Collection '{COLLECTION}' supprimée.")
        else:
            count = info["result"]["points_count"]
            print(f"  Collection '{COLLECTION}' existante ({count} points).")
            return
    except Exception:
        pass
    _http("PUT", f"{QDRANT}/collections/{COLLECTION}", {
        "vectors": {"size": 768, "distance": "Cosine"}
    })
    print(f"  Collection '{COLLECTION}' créée.")

# ── Embedding ─────────────────────────────────────────────────────────────────
def embed(text: str) -> list:
    data = _http("POST", f"{OLLAMA}/api/embeddings",
                 {"model": EMBED_MODEL, "prompt": text})
    return data["embedding"]

# ── Chunking ──────────────────────────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
    text   = " ".join(text.split())  # normalise whitespace
    chunks = []
    start  = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        # Coupure propre sur espace si possible
        if end < len(text):
            cut = text.rfind(" ", start, end)
            if cut > start:
                end = cut
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if len(c) > 50]

# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  [!] pypdf non installé — pip install pypdf")
        return ""
    reader = PdfReader(str(path))
    return "\n".join(p.extract_text() or "" for p in reader.pages)

def parse_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        print("  [!] python-docx non installé — pip install python-docx")
        return ""
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)

PARSERS = {
    ".txt":  parse_txt,
    ".md":   parse_txt,
    ".pdf":  parse_pdf,
    ".docx": parse_docx,
}

# ── Ingestion ─────────────────────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def ingest_file(path: Path, state: dict) -> int:
    suffix = path.suffix.lower()
    if suffix not in PARSERS:
        return 0

    fhash = file_hash(path)
    key   = str(path.relative_to(BASE))

    if state.get(key) == fhash:
        print(f"  [=] {path.name} (déjà indexé)")
        return 0

    parser = PARSERS[suffix]
    text   = parser(path).strip()
    if not text:
        print(f"  [!] {path.name} — vide ou non parseable")
        return 0

    chunks = chunk_text(text)
    print(f"  [+] {path.name}  →  {len(chunks)} chunks", end="", flush=True)

    points = []
    for i, chunk in enumerate(chunks):
        try:
            vector = embed(chunk)
        except Exception as e:
            print(f"\n  [!] Embedding échoué pour chunk {i}: {e}")
            continue
        points.append({
            "id": int(time.time() * 1000) + i,
            "vector": vector,
            "payload": {
                "filename":    path.name,
                "filepath":    key,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "text":        chunk,
                "source":      "docs",
                "hash":        fhash,
            },
        })
        print(".", end="", flush=True)
        time.sleep(0.05)  # évite de surcharger Ollama

    if points:
        # Insérer par batch de 50
        for i in range(0, len(points), 50):
            _http("POST", f"{QDRANT}/collections/{COLLECTION}/points",
                  {"points": points[i:i+50]})

    state[key] = fhash
    print(f"  ({len(points)} vecteurs)")
    return len(points)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Vide la collection avant d'ingérer")
    parser.add_argument("--dir", default=str(DOCS_DIR),
                        help="Dossier source (défaut: docs/)")
    args = parser.parse_args()

    docs_dir = Path(args.dir)
    if not docs_dir.exists():
        print(f"Dossier introuvable: {docs_dir}")
        sys.exit(1)

    print(f"\n  Jarvis — Ingestion de documents")
    print(f"  Dossier : {docs_dir}")
    print(f"  Qdrant  : {QDRANT}  |  Collection : {COLLECTION}")
    print(f"  Modèle  : {EMBED_MODEL}\n")

    ensure_collection(reset=args.reset)
    state = load_state() if not args.reset else {}

    files = sorted(docs_dir.rglob("*"))
    files = [f for f in files if f.is_file() and not f.name.startswith(".")]

    if not files:
        print("\n  Aucun fichier dans docs/ — dépose des PDF/TXT/DOCX/MD et relance.")
        return

    total = 0
    for f in files:
        total += ingest_file(f, state)

    save_state(state)
    print(f"\n  Terminé — {total} vecteurs insérés dans '{COLLECTION}'.")
    print(f"  Tes documents sont maintenant disponibles pour Jarvis IA.\n")

if __name__ == "__main__":
    main()
