# ShopSense: AI Shopping Assistant for Visually Impaired Users

> *From "relying on others to describe" to "making independent, informed decisions."*

ShopSense is a voice-first shopping assistant built for visually impaired users. Using a multi-modal ReAct agent, it transforms product images and thousands of reviews into trustworthy, perceivable purchase recommendations.


---

## The Problem

Visually impaired shoppers face two critical gaps when shopping online:

- **Visual information is inaccessible**: The most important product details — style, color, material texture — are locked inside images. Screen readers can only surface minimal alt text.
- **Review overload**: Thousands of reviews are a useful resource for sighted users, but an auditory burden for visually impaired users who need specific answers about button placement, material feel, or ease of wear.

---

## What ShopSense Does

### Hear the Image (Visual Sense)
Retrieves pre-generated semantic visual descriptions of product images, translated into natural, conversational language optimized for text-to-speech playback.

### Smart Review Retrieval (Review Intelligence)
Semantic search over customer reviews, filtered by reviewer body type, sentiment, and verified purchase status. For example: *"Find sizing feedback from reviewers around 180cm tall."*

### Conflict Detection (Dual Verification)
ShopSense's original feature. Automatically compares official product descriptions against real buyer feedback. If the listing says "extremely warm" but reviewers say "thin," the system surfaces a risk warning rather than giving a misleading answer.

---

## Architecture: ReAct Reasoning Loop

ShopSense uses a **Thought → Action → Observation** iterative loop (up to 3 iterations) to ensure every recommendation is grounded in evidence. Based on the question's intent, the agent autonomously selects which tools to call, evaluates the results, and decides whether to search further before generating a final answer.

### Agent Tools

| Tool | Description |
|---|---|
| `visual_search` | Semantic retrieval over pre-generated image descriptions. Supports natural language queries like "What is the shoulder strap material?" |
| `review_search` | Multi-dimensional review search. Filter by reviewer height/weight, sentiment, rating, and verified purchase status. |
| `knowledge_search` | Professional knowledge base covering fabrics, thermal ratings, skin compatibility, and care instructions. |

### Conflict Detection System

One of ShopSense's original contributions. The agent continuously cross-checks official product claims against real buyer feedback across 5 dimensions: skin sensitivity, sizing accuracy, warmth, water resistance, and durability.

**Example**: If the official listing says "extremely warm" but multiple reviews say "the fabric is thin," the agent does not echo the official claim. Instead it surfaces a warning:
> *"Official description conflicts with buyer reviews — warmth claims may be overstated. Several reviewers noted thin fabric."*

This prevents users from making purchasing decisions based on misleading product copy.

### Reflection & Quality Control

Before generating a final answer, the agent runs a self-evaluation (`_reflect`) to assess whether the retrieved data is sufficient. If it detects gaps, it either switches tools to gather more information, or honestly tells the user that the evidence is inconclusive — avoiding AI hallucination-driven purchase errors.

After each iteration, retrieval summaries, detected conflicts, and identified gaps are re-injected into the LLM context, so every reasoning step builds on everything gathered so far.

### Accessibility-First Output

- **Conclusion-first format**: The first sentence is always a direct verdict (Yes / No / Likely / Unclear) — no lengthy preamble.
- **Screen reader friendly**: Special characters (%, /, ★) are always spelled out. Maximum 2–3 sentences per answer for natural TTS playback.
- **Built-in TTS**: Integrated with OpenAI TTS (`tts-1-hd`) and DashScope CosyVoice, with automatic fallback to browser Web Speech API.
- **Voice input**: Both the product search page and the Q&A input support speech-to-text via the browser Web Speech API. Activate by clicking the microphone button or pressing **⌥V** (Mac) / **Alt+V** (Windows). On the Q&A page, recognized speech is read back via TTS and submitted automatically.

---

## Tech Stack

| Component | Technology |
|---|---|
| Vector DB | Qdrant Cloud |
| LLM | Llama 3.3 70B via Groq (OpenAI-compatible API) |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers (local, no API key required) |
| Backend | FastAPI |
| Frontend | React + Vite (ARIA-compliant) |

---

## Project Structure

```
shopsense/
├── agent/
│   ├── react.py              # Core ReAct reasoning loop
│   └── tools/                # Tool implementations (review, knowledge, visual)
├── backend/main.py           # FastAPI server & API endpoints
├── frontend/                 # React + Vite UI
├── core/embeddings.py        # Local embedding model (all-MiniLM-L6-v2)
├── config/settings.py        # Central config (reads from .env)
├── data/                     # JSON data files (products, reviews, knowledge, visual)
├── scripts/
│   ├── setup_collections.py  # Create Qdrant collections (run once)
│   ├── ingest_all.py         # Load data into Qdrant (run once)
│   └── generate_visual_descriptions.py  # Pre-generate image descriptions
├── launch.sh                 # One-command startup script
├── requirements.txt
└── .env.example
```

---

## Quickstart

### 1. Configure API Keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

Required keys:
- **`QDRANT_URL` / `QDRANT_API_KEY`** — [Qdrant Cloud](https://cloud.qdrant.io) free cluster
- **`DASHSCOPE_API_KEY`** — [Groq](https://console.groq.com) free API (or any OpenAI-compatible endpoint)

Optional (for neural TTS):
- **`OPENAI_API_KEY`** — enables OpenAI `tts-1-hd` voice synthesis

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Qdrant (first run only)

```bash
# Create collections
python scripts/setup_collections.py

# Ingest data (downloads embedding model ~90MB on first run)
python scripts/ingest_all.py
```

### 4. Start the Project

**Option A — One command:**
```bash
bash launch.sh
```

**Option B — Manual:**
```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173)

---

## Notes

- First run of `ingest_all.py` downloads `all-MiniLM-L6-v2` (~90MB) — requires internet access
- The `.env` file is gitignored — never commit real API keys
- Qdrant Cloud free tier is sufficient to run this project
- Groq free tier daily token limits are sufficient for normal use

---

## Roadmap

- [x] Multi-turn tool-calling agent with ReAct framework
- [x] Cross-dimensional review and visual semantic retrieval
- [x] Automatic conflict detection and risk warning system
- [x] Agent transparency panel (ReAct trace, retrieval scores, conflict signals)
- [x] Accessibility themes: high contrast, light, dark
- [x] Voice input (Web Speech API) with keyboard shortcut (⌥V / Alt+V) and TTS confirmation
- [ ] Real-time multimodal image analysis (GPT-4o / Claude)
- [ ] Chrome / Amazon browser extension
- [ ] Multi-turn continuous voice conversation
