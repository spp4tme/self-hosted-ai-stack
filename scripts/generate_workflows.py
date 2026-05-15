"""
Génère les workflows n8n avec le code JS correctement échappé.
"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────────────────────
# RAG + Entity Memory — code JS
# ─────────────────────────────────────────────────────────────────────────────
RAG_JS = r"""
const OLLAMA            = 'http://host.docker.internal:11434';
const QDRANT            = 'http://host.docker.internal:6333';
const SEARXNG           = 'http://host.docker.internal:8888';
const COLLECTION        = 'jarvis_memory';
const ENTITY_COLLECTION = 'jarvis_entities';
const DOCS_COLLECTION   = 'jarvis_docs';
const EMBED_MODEL       = 'nomic-embed-text';
const CHAT_MODEL        = 'llama3.2';
const TOP_K             = 3;
const SCORE_MEM         = 0.6;
const SCORE_ENT         = 0.5;
const SCORE_DOCS        = 0.55;

async function ollamaPost(path, body) {
  const r = await fetch(`${OLLAMA}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Ollama ${path} => ${r.status}`);
  return r.json();
}

async function qdrantReq(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${QDRANT}${path}`, opts);
  if (!r.ok) throw new Error(`Qdrant ${method} ${path} => ${r.status}`);
  return r.json();
}

async function ensureCollection(name) {
  try { const r = await fetch(`${QDRANT}/collections/${name}`); if (r.ok) return; } catch (_) {}
  await qdrantReq('PUT', `/collections/${name}`, { vectors: { size: 768, distance: 'Cosine' } });
}

async function getEmbedding(text) {
  const d = await ollamaPost('/api/embeddings', { model: EMBED_MODEL, prompt: text });
  return d.embedding;
}

async function searchQdrant(collection, vector, limit, threshold) {
  try {
    const d = await qdrantReq('POST', `/collections/${collection}/points/search`, {
      vector, limit, score_threshold: threshold, with_payload: true,
    });
    return d.result || [];
  } catch (e) { console.log(`Qdrant search ${collection} failed:`, e.message); return []; }
}

async function searchWeb(query) {
  try {
    const url = `${SEARXNG}/search?q=${encodeURIComponent(query)}&format=json&language=fr-FR`;
    const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return [];
    const d = await r.json();
    return (d.results || []).slice(0, 3).map(x => ({ title: x.title || '', url: x.url || '', content: x.content || x.snippet || '' }));
  } catch (e) { console.log('SearXNG failed:', e.message); return []; }
}

// ── Entity memory ─────────────────────────────────────────────────────────────
async function extractEntities(question, answer) {
  try {
    const prompt = `Extrait les faits concrets et réutilisables de cet échange.
Q: ${question}
R: ${answer}

Retourne UNIQUEMENT un tableau JSON (5 max, ou [] si rien) :
[{"type":"preference|projet|tech|personne|fait","name":"nom_court","value":"la valeur"}]`;
    const d = await ollamaPost('/api/generate', {
      model: CHAT_MODEL, prompt, stream: false, format: 'json',
      options: { temperature: 0.1, num_predict: 200 },
    });
    const m = (d.response || '[]').match(/\[[\s\S]*\]/);
    return m ? JSON.parse(m[0]) : [];
  } catch (e) { console.log('Entity extraction failed:', e.message); return []; }
}

async function storeEntities(entities) {
  if (!entities || entities.length === 0) return 0;
  await ensureCollection(ENTITY_COLLECTION);
  let stored = 0;
  for (const ent of entities) {
    if (!ent.name || !ent.value) continue;
    try {
      const text = `${ent.type || 'fait'}: ${ent.name} = ${ent.value}`;
      const emb  = await getEmbedding(text);
      await qdrantReq('POST', `/collections/${ENTITY_COLLECTION}/points`, {
        points: [{ id: Date.now() + Math.floor(Math.random() * 999), vector: emb,
          payload: { entity_type: ent.type || 'fait', name: ent.name, value: ent.value, timestamp: new Date().toISOString() } }],
      });
      stored++;
    } catch (e) { console.log('Entity store error:', e.message); }
  }
  return stored;
}

// ── Gesture → prompt ──────────────────────────────────────────────────────────
const gesturePrompts = {
  STOP:     'Donne-moi un point de situation rapide.',
  NAVIGATE: 'Fais une recherche sur les actualites du moment et dis-moi les points importants.',
  SELECT:   'Fais un resume concis de notre conversation.',
  VALIDATE: 'Confirme et resume la derniere action demandee.',
  SCROLL:   'Propose-moi 3 nouvelles idees ou pistes de reflexion.',
  MODE:     'Tu viens de passer en mode IA. Comment puis-je t aider ?',
};

const systemPrompt = `Tu es Jarvis, un assistant IA personnel intégré à un système de contrôle gestuel.
Tu réponds en français, de façon concise (2-4 phrases max sauf si demandé autrement).
Tu as accès à la mémoire des échanges précédents et aux faits connus sur l'utilisateur.`;

// ── Main ──────────────────────────────────────────────────────────────────────
const input   = items[0].json;
const gesture = (input.gesture || 'STOP').toUpperCase();
const mode    = (input.mode    || 'IA').toUpperCase();
const extra   = input.extra || '';

const userPrompt = gesturePrompts[gesture] || gesturePrompts.STOP;
const fullPrompt = extra ? `${userPrompt}\n\nContexte: ${extra}` : userPrompt;

let embedding = null, memoryHits = [], entityHits = [], docsHits = [], webResults = [];
let memStored = false, entStored = 0;

// a) Embedding
try { embedding = await getEmbedding(fullPrompt); } catch (e) { console.log('Embed failed:', e.message); }

// b) Memory + entity + docs search
if (embedding) {
  await ensureCollection(COLLECTION);
  memoryHits = await searchQdrant(COLLECTION, embedding, TOP_K, SCORE_MEM);
  entityHits = await searchQdrant(ENTITY_COLLECTION, embedding, 5, SCORE_ENT);
  docsHits   = await searchQdrant(DOCS_COLLECTION,   embedding, 4, SCORE_DOCS);
}

// c) Web search (NAVIGATE only)
if (gesture === 'NAVIGATE') webResults = await searchWeb(extra || 'actualites technologie IA');

// d) Build messages
const messages = [{ role: 'system', content: systemPrompt }];

if (entityHits.length > 0) {
  messages.push({ role: 'system', content:
    'Faits connus sur l utilisateur:\n' +
    entityHits.map(h => `${h.payload.entity_type}: ${h.payload.name} = ${h.payload.value}`).join('\n')
  });
}

if (memoryHits.length > 0) {
  messages.push({ role: 'system', content:
    'Echanges precedents pertinents:\n' +
    memoryHits.map(h => `Q: ${h.payload.question}\nR: ${h.payload.answer}`).join('\n---\n')
  });
}

if (docsHits.length > 0) {
  messages.push({ role: 'system', content:
    'Extraits de tes documents personnels (priorité haute) :\n' +
    docsHits.map(h => `[${h.payload.filename}]\n${h.payload.text}`).join('\n---\n')
  });
}

if (webResults.length > 0) {
  messages.push({ role: 'system', content:
    'Resultats web:\n' +
    webResults.map((r, i) => `[${i+1}] ${r.title}\n${r.content}\n${r.url}`).join('\n---\n')
  });
}

messages.push({ role: 'user', content: fullPrompt });

// e) Ollama chat
let response = 'Désolée, je ne peux pas répondre pour le moment.';
try {
  const d = await ollamaPost('/api/chat', { model: CHAT_MODEL, messages, stream: false, options: { temperature: 0.7, num_predict: 300 } });
  response = d.message?.content || response;
} catch (e) { response = `Erreur Ollama: ${e.message}`; }

// f) Store Q+A
if (embedding) {
  try {
    await qdrantReq('POST', `/collections/${COLLECTION}/points`, {
      points: [{ id: Date.now(), vector: embedding, payload: { question: fullPrompt, answer: response, timestamp: new Date().toISOString() } }],
    });
    memStored = true;
  } catch (e) { console.log('Memory store failed:', e.message); }
}

// g) Extract + store entities
if (memStored) {
  const entities = await extractEntities(fullPrompt, response);
  entStored = await storeEntities(entities);
}

const result = { response, gesture, mode, memory_stored: memStored, entities_stored: entStored, memory_hits: memoryHits.length, entity_hits: entityHits.length, doc_hits: docsHits.length };
if (webResults.length > 0) result.sources = webResults.map(r => ({ title: r.title, url: r.url }));

return [{ json: result }];
""".strip()

# ─────────────────────────────────────────────────────────────────────────────
# Agent ReAct — code JS
# ─────────────────────────────────────────────────────────────────────────────
AGENT_JS = r"""
// Jarvis Agent ReAct — résout des tâches en utilisant des outils
// Receives: { task?, gesture?, context? }
// Returns:  { response, steps, iterations_used, task }

const AGENT   = 'http://host.docker.internal:9999';
const OLLAMA  = 'http://host.docker.internal:11434';
const SEARXNG = 'http://host.docker.internal:8888';
const CHAT_MODEL = 'llama3.2';
const MAX_ITER   = 8;

const TOOL_DOCS = `Outils disponibles :
- list_files  : Liste les fichiers d un dossier.  Args: {"path":"C:\\\\Users\\\\antho\\\\Documents\\\\mon-ia"}
- read_file   : Lit le contenu d un fichier.      Args: {"path":"C:\\\\chemin\\\\fichier.txt"}
- write_file  : Ecrit dans un fichier.            Args: {"path":"C:\\\\chemin\\\\fichier.txt","content":"texte"}
- run_python  : Execute du code Python.           Args: {"code":"print('hello')"}
- web_search  : Recherche sur le web.             Args: {"query":"termes de recherche"}`;

const SYSTEM = `Tu es Jarvis, un agent IA autonome sur une machine Windows.
Tu résous des tâches étape par étape en utilisant des outils.

${TOOL_DOCS}

Pour appeler un outil, réponds UNIQUEMENT avec ce format exact :
TOOL: nom_outil
ARGS: {"cle":"valeur"}

Quand la tâche est terminée, réponds UNIQUEMENT avec :
FINAL: ta réponse complète

Règles :
- Utilise des chemins Windows absolus (C:\\\\Users\\\\antho\\\\Documents\\\\mon-ia\\\\...)
- L accès aux fichiers est limité à C:\\\\Users\\\\antho\\\\Documents\\\\mon-ia\\\\
- Sois efficace : n utilise les outils que si nécessaire
- Réponds en français`;

async function executeTool(name, args) {
  if (name === 'web_search') {
    const q = encodeURIComponent(args.query || '');
    const r = await fetch(`${SEARXNG}/search?q=${q}&format=json&language=fr-FR`, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return 'Recherche web indisponible';
    const d = await r.json();
    return (d.results || []).slice(0, 3).map(x => `[${x.title}]\n${x.content || ''}\n${x.url}`).join('\n---\n') || 'Aucun résultat';
  }

  const isPost = ['read_file', 'write_file', 'run_python'].includes(name);
  let url = `${AGENT}/tool/${name}`;
  const opts = { signal: AbortSignal.timeout(20000) };

  if (isPost) {
    opts.method  = 'POST';
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body    = JSON.stringify(args);
  } else {
    opts.method = 'GET';
    const params = new URLSearchParams(args).toString();
    if (params) url += `?${params}`;
  }

  const r = await fetch(url, opts);
  const d = await r.json();
  if (!d.ok) throw new Error(d.error || 'Tool error');

  if (d.content !== undefined) return d.content;
  if (d.output  !== undefined) return d.output;
  if (d.items   !== undefined) return JSON.stringify(d.items, null, 2);
  return JSON.stringify(d);
}

function parseResponse(text) {
  const toolM  = text.match(/TOOL:\s*(\w+)/);
  const argsM  = text.match(/ARGS:\s*(\{[\s\S]*?\})/);
  const finalM = text.match(/FINAL:\s*([\s\S]+)/);
  if (finalM) return { type: 'final', content: finalM[1].trim() };
  if (toolM) {
    let args = {};
    if (argsM) { try { args = JSON.parse(argsM[1]); } catch (_) {} }
    return { type: 'tool', tool: toolM[1].trim(), args };
  }
  return { type: 'unknown', content: text };
}

const gestureTasks = {
  STOP:     'Donne-moi un résumé de l état actuel du projet mon-ia en listant les fichiers principaux.',
  NAVIGATE: 'Cherche les dernières nouveautés en IA locale (Ollama, LLM open-source) et résume les 3 points importants.',
  SELECT:   'Liste tous les fichiers Python du projet mon-ia et dis-moi lequel a été modifié le plus récemment.',
  VALIDATE: 'Vérifie que les fichiers de configuration du projet sont cohérents (config.json, docker-compose.yaml).',
  SCROLL:   'Propose 3 améliorations concrètes au projet mon-ia avec des exemples de code si pertinent.',
};

// ── Main ──────────────────────────────────────────────────────────────────────
const input   = items[0].json;
const gesture = (input.gesture || 'NAVIGATE').toUpperCase();
const task    = input.task || gestureTasks[gesture] || gestureTasks.NAVIGATE;

const messages = [
  { role: 'system', content: SYSTEM },
  { role: 'user',   content: task },
];

const steps = [];
let iterationsUsed = 0;
let finalResponse  = null;

for (let i = 0; i < MAX_ITER; i++) {
  iterationsUsed = i + 1;

  let llmText = '';
  try {
    const r = await fetch(`${OLLAMA}/api/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: CHAT_MODEL, messages, stream: false, options: { temperature: 0.2, num_predict: 512 } }),
      signal: AbortSignal.timeout(60000),
    });
    const d = await r.json();
    llmText = d.message?.content || '';
  } catch (e) { finalResponse = `Erreur Ollama: ${e.message}`; break; }

  messages.push({ role: 'assistant', content: llmText });
  const parsed = parseResponse(llmText);

  if (parsed.type === 'final') { finalResponse = parsed.content; break; }

  if (parsed.type === 'tool') {
    const step = { iteration: i + 1, tool: parsed.tool, args: parsed.args };
    let toolResult = '';
    try {
      toolResult = await executeTool(parsed.tool, parsed.args);
      step.result = toolResult.slice(0, 2000);
    } catch (e) { toolResult = `Erreur outil: ${e.message}`; step.error = e.message; }
    steps.push(step);
    messages.push({ role: 'user', content: `Résultat de ${parsed.tool}:\n${toolResult}\n\nContinue.` });
  } else {
    finalResponse = llmText;
    break;
  }
}

if (!finalResponse) finalResponse = 'Limite d itérations atteinte. Résultat partiel:\n' + (steps.at(-1)?.result || '');

return [{ json: { response: finalResponse, task, gesture, steps, iterations_used: iterationsUsed } }];
""".strip()

# ─────────────────────────────────────────────────────────────────────────────
# Génération des fichiers JSON
# ─────────────────────────────────────────────────────────────────────────────

def make_node(id_, name, js_code, x, y):
    return {
        "parameters": {
            "mode": "runOnceForAllItems",
            "language": "javaScript",
            "jsCode": js_code,
        },
        "id": id_,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x, y],
    }

def make_webhook(id_, name, path, webhook_id, x, y):
    return {
        "parameters": {
            "httpMethod": "POST",
            "path": path,
            "responseMode": "lastNode",
            "options": {},
        },
        "id": id_,
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [x, y],
        "webhookId": webhook_id,
    }

def make_workflow(name, webhook_node, code_node, tags, wf_id, version_id):
    return {
        "name": name,
        "nodes": [webhook_node, code_node],
        "connections": {
            webhook_node["name"]: {
                "main": [[{"node": code_node["name"], "type": "main", "index": 0}]]
            }
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": version_id,
        "id": wf_id,
        "tags": [{"name": t} for t in tags],
    }

# ── jarvis_ia_complete.json ───────────────────────────────────────────────────
rag_workflow = make_workflow(
    name       = "Jarvis IA — RAG + Entity Memory",
    webhook_node = make_webhook("webhook-jarvis", "Webhook", "jarvis", "jarvis-gesture-webhook", 240, 300),
    code_node    = make_node("rag-pipeline", "RAG Pipeline", RAG_JS, 480, 300),
    tags         = ["jarvis", "rag", "entity-memory"],
    wf_id        = "jarvis-rag-complete",
    version_id   = "jarvis-v3",
)

# ── jarvis_agent.json ─────────────────────────────────────────────────────────
agent_workflow = make_workflow(
    name       = "Jarvis Agent — ReAct + Outils",
    webhook_node = make_webhook("webhook-agent", "Webhook Agent", "jarvis-agent", "jarvis-agent-webhook", 240, 300),
    code_node    = make_node("agent-loop", "Agent Loop", AGENT_JS, 480, 300),
    tags         = ["jarvis", "agent", "tools"],
    wf_id        = "jarvis-react-agent",
    version_id   = "jarvis-agent-v1",
)

out_dir = os.path.join(BASE, "n8n", "workflows")
os.makedirs(out_dir, exist_ok=True)

rag_path   = os.path.join(out_dir, "jarvis_ia_complete.json")
agent_path = os.path.join(out_dir, "jarvis_agent.json")

with open(rag_path, "w", encoding="utf-8") as f:
    json.dump(rag_workflow, f, ensure_ascii=False, indent=2)

with open(agent_path, "w", encoding="utf-8") as f:
    json.dump(agent_workflow, f, ensure_ascii=False, indent=2)

print(f"OK  {rag_path}")
print(f"OK  {agent_path}")
