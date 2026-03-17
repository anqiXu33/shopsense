# ShopSense
**Accessible Shopping Assistant for Visually Impaired Users**
Qdrant Hackathon 2025 — Context Engineering Track

---

## Stack
| Component | Technology |
|---|---|
| Vector DB | Qdrant Cloud |
| LLM | Groq (llama-3.3-70b, OpenAI-compatible) |
| Embeddings | sentence-transformers (local, no API key) |
| Backend | FastAPI |
| Frontend | React + Vite |

---

## Project Structure
```
shopsense/
├── config/settings.py       # Central config (reads from .env)
├── core/embeddings.py       # Local embedding model (all-MiniLM-L6-v2)
├── backend/main.py          # FastAPI server
├── frontend/                # React + Vite UI
├── data/                    # JSON data files
├── scripts/
│   ├── setup_collections.py # Create Qdrant collections (run once)
│   └── ingest_all.py        # Load data into Qdrant (run once)
├── requirements.txt
└── .env.example
```

---

## Quickstart

### 1. 配置 API Keys

```bash
cp .env.example .env
# 编辑 .env，填入你自己的 key
```

需要的 key：
- **QDRANT_URL / QDRANT_API_KEY** — [Qdrant Cloud](https://cloud.qdrant.io) 免费集群
- **DASHSCOPE_API_KEY** — [Groq](https://console.groq.com) 免费 API（或其他 OpenAI 兼容接口）

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化 Qdrant（首次运行）

```bash
# 创建 collections
python scripts/setup_collections.py

# 导入数据（会自动下载 embedding 模型，约 90MB）
python scripts/ingest_all.py
```

### 4. 启动后端

```bash
cd backend
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

## 注意事项

- 首次运行 `ingest_all.py` 时会自动下载 `all-MiniLM-L6-v2` 模型（约 90MB），需要联网
- `.env` 文件已加入 `.gitignore`，**不要**将真实 API key 提交到仓库
- Qdrant Cloud 免费套餐足够运行本项目
- Groq 免费套餐每天有 token 限额，正常体验足够
