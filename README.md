# ShopSense 🛍️
**Accessible Shopping Assistant for Visually Impaired Users**
Qdrant Hackathon 2025 — Context Engineering Track

---

## Stack
| Component | Technology | Why |
|---|---|---|
| Vector DB | Qdrant Cloud | Hackathon requirement |
| Vision Model | LLaVA-1.5 (HuggingFace) | Free, strong multimodal |
| LLM | Mistral-7B-Instruct (HF API) | Free tier, good instruction-following |
| Embeddings | sentence-transformers (local) | No API cost |
| UI | Gradio | Fast to build, researcher-friendly |

---

## Project Structure
```
shopsense/
├── config/
│   └── settings.py          # API keys, model names, Qdrant config
├── data/
│   └── sample_products.json # Demo product dataset (30 products)
├── scripts/
│   ├── ingest.py            # Load products → Qdrant (run once)
│   └── build_knowledge.py   # Build material knowledge base
├── agent/
│   ├── tools.py             # Visual analysis, Qdrant search tools
│   ├── intent.py            # Intent classifier + entity extractor
│   ├── planner.py           # Task planner (DAG mode)
│   ├── context_engineer.py  # Context assembly with token budgeting
│   └── agent.py             # Main agent loop
├── frontend/
│   └── app.py               # Gradio UI
├── requirements.txt
└── README.md
```

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API keys in config/settings.py

# 3. Ingest data into Qdrant (run once)
python scripts/ingest.py

# 4. Launch the app
python frontend/app.py
```
