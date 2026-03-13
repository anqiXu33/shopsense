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

## Quickstart (React + FastAPI)

### 1. 配置 API Keys

创建 `.env` 文件（参考 `config/settings.py`）：
```
DASHSCOPE_API_KEY=your_key_here
QDRANT_URL=http://127.0.0.1:6333
```

### 2. 启动 Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 3. 导入数据（首次运行）

```bash
pip install -r requirements.txt
python scripts/ingest_v2.py
```

### 4. 启动后端

```bash
cd backend
pip install fastapi uvicorn
uvicorn main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

---

### 快速体验（Mock 模式，无需 API Key）

仅启动后端和前端即可体验 UI（回答为模拟数据）：
```bash
# 终端 1
cd backend && uvicorn main:app --reload --port 8000

# 终端 2
cd frontend && npm install && npm run dev
```

---

## Quickstart (Legacy Gradio)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API keys in config/settings.py

# 3. Ingest data into Qdrant (run once)
python scripts/ingest.py

# 4. Launch the app
python frontend/app.py
```
