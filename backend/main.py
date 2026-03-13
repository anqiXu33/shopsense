"""
backend/main.py
FastAPI backend for ShopSense v2.

Run:
    cd backend
    pip install fastapi uvicorn
    uvicorn main:app --reload --port 8000
"""

import asyncio
import sys
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="ShopSense API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mock Data ────────────────────────────────────────────────────────────────

MOCK_PRODUCTS = [
    {
        "asin": "P001",
        "name": "Alpine Duck Down Jacket",
        "brand": "NorthPeak",
        "category": "outerwear",
        "price": 129.99,
        "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=800&q=80",
        "description": "Duck down fill 450g, deep navy blue color, wind-resistant matte shell, removable hood with adjustable drawstring, two zip side pockets and one inner chest pocket, ribbed cuffs, slightly fitted silhouette, logo patch on left chest.",
        "rating": 3.7,
        "review_count": 6,
        "attributes": {"color": "navy blue", "material": "duck down + polyester shell"},
    },
    {
        "asin": "P002",
        "name": "Waterproof Trench Coat",
        "brand": "UrbanShell",
        "category": "outerwear",
        "price": 189.99,
        "image_url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?auto=format&fit=crop&w=800&q=80",
        "description": "100% polyester with waterproof membrane, classic khaki beige, double-breasted button front, belted waist, storm flap at shoulders, knee length, removable wool-blend inner lining, structured collar.",
        "rating": 4.2,
        "review_count": 5,
        "attributes": {"color": "khaki beige", "material": "polyester + waterproof membrane"},
    },
    {
        "asin": "P003",
        "name": "Merino Wool Turtleneck",
        "brand": "WoolCraft",
        "category": "knitwear",
        "price": 89.99,
        "image_url": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=800&q=80",
        "description": "100% extra-fine merino wool, classic ivory white, ribbed turtleneck collar, relaxed fit, temperature-regulating and naturally odor-resistant. Safe for sensitive skin.",
        "rating": 4.6,
        "review_count": 8,
        "attributes": {"color": "ivory white", "material": "100% merino wool"},
    },
    {
        "asin": "P004",
        "name": "Cashmere Blend Scarf",
        "brand": "LuxeKnit",
        "category": "accessories",
        "price": 59.99,
        "image_url": "https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?auto=format&fit=crop&w=800&q=80",
        "description": "70% cashmere 30% silk, warm camel brown, 180cm length, fringe edges, ultra-lightweight and exceptionally warm for its weight.",
        "rating": 4.8,
        "review_count": 12,
        "attributes": {"color": "camel brown", "material": "cashmere + silk blend"},
    },
    {
        "asin": "P005",
        "name": "Fleece Zip-Up Hoodie",
        "brand": "CozyLayer",
        "category": "casual",
        "price": 49.99,
        "image_url": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?auto=format&fit=crop&w=800&q=80",
        "description": "100% recycled polyester fleece, heather grey, full-zip front, kangaroo pocket, adjustable hood, relaxed fit. Brushed interior for extra softness.",
        "rating": 4.3,
        "review_count": 15,
        "attributes": {"color": "heather grey", "material": "recycled polyester fleece"},
    },
    {
        "asin": "P006",
        "name": "Cotton Oxford Shirt",
        "brand": "ClassicFit",
        "category": "shirts",
        "price": 45.99,
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=800&q=80",
        "description": "100% cotton oxford weave, crisp white, button-down collar, chest pocket, slim fit, machine washable. Breathable and comfortable for all-day wear.",
        "rating": 4.1,
        "review_count": 20,
        "attributes": {"color": "white", "material": "100% cotton"},
    },
    {
        "asin": "P007",
        "name": "Thermal Base Layer Set",
        "brand": "ThermoCore",
        "category": "activewear",
        "price": 69.99,
        "image_url": "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?auto=format&fit=crop&w=800&q=80",
        "description": "Merino wool blend, charcoal grey, moisture-wicking, quick-dry, flatlock seams to prevent chafing. Top and bottom set, ideal for winter sports and cold commutes.",
        "rating": 4.5,
        "review_count": 9,
        "attributes": {"color": "charcoal grey", "material": "merino wool blend"},
    },
    {
        "asin": "P008",
        "name": "Windproof Softshell Jacket",
        "brand": "TrailBlaze",
        "category": "outerwear",
        "price": 159.99,
        "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=800&q=80",
        "description": "3-layer softshell fabric, forest green, windproof and water-resistant, articulated stretch panels for freedom of movement, zippered chest and hand pockets.",
        "rating": 4.4,
        "review_count": 7,
        "attributes": {"color": "forest green", "material": "softshell polyester"},
    },
    {
        "asin": "P009",
        "name": "Linen Summer Shirt",
        "brand": "BreezeWear",
        "category": "shirts",
        "price": 55.99,
        "image_url": "https://images.unsplash.com/photo-1607345366928-199ea26cfe3e?auto=format&fit=crop&w=800&q=80",
        "description": "100% Belgian linen, sky blue, relaxed fit, chest pocket, single button cuffs. Naturally breathable and lightweight, ideal for warm weather and humid climates.",
        "rating": 4.2,
        "review_count": 11,
        "attributes": {"color": "sky blue", "material": "100% Belgian linen"},
    },
    {
        "asin": "P010",
        "name": "Quilted Puffer Vest",
        "brand": "AlpineStyle",
        "category": "outerwear",
        "price": 89.99,
        "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=800&q=80",
        "description": "Synthetic fill, matte black, quilted diamond stitching, full-zip front, interior security pocket, slim fit, packable into its own pocket.",
        "rating": 4.0,
        "review_count": 6,
        "attributes": {"color": "matte black", "material": "synthetic fill + nylon shell"},
    },
    {
        "asin": "P011",
        "name": "Stretch Denim Jeans",
        "brand": "DenimLab",
        "category": "bottoms",
        "price": 95.99,
        "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=800&q=80",
        "description": "98% cotton 2% elastane, indigo blue, slim straight cut, five-pocket design, reinforced belt loops, slightly tapered at the ankle.",
        "rating": 4.3,
        "review_count": 18,
        "attributes": {"color": "indigo blue", "material": "cotton + elastane"},
    },
    {
        "asin": "P012",
        "name": "Bamboo Lounge Set",
        "brand": "EcoComfort",
        "category": "loungewear",
        "price": 75.99,
        "image_url": "https://images.unsplash.com/photo-1585487000160-6ebcfceb0d03?auto=format&fit=crop&w=800&q=80",
        "description": "95% bamboo viscose 5% spandex, sage green, ultra-soft to touch, naturally antibacterial and temperature-regulating. Relaxed top and tapered pants set.",
        "rating": 4.7,
        "review_count": 14,
        "attributes": {"color": "sage green", "material": "bamboo viscose"},
    },
    {
        "asin": "P013",
        "name": "Merino Running Socks",
        "brand": "SockTech",
        "category": "accessories",
        "price": 29.99,
        "image_url": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=800&q=80",
        "description": "60% merino wool, crew length, cushioned sole, arch support band, moisture-wicking and odor-resistant. 3-pack. Suitable for running, hiking, and everyday wear.",
        "rating": 4.6,
        "review_count": 22,
        "attributes": {"color": "white/grey mix", "material": "merino wool blend"},
    },
    {
        "asin": "P014",
        "name": "Corduroy Overshirt",
        "brand": "LayerUp",
        "category": "shirts",
        "price": 79.99,
        "image_url": "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?auto=format&fit=crop&w=800&q=80",
        "description": "100% cotton corduroy, rust orange, oversized shirt-jacket silhouette, two chest pockets with button flaps, button front, versatile as both a shirt and light outer layer.",
        "rating": 4.2,
        "review_count": 8,
        "attributes": {"color": "rust orange", "material": "100% cotton corduroy"},
    },
    {
        "asin": "P015",
        "name": "Long Down Blanket Coat",
        "brand": "CoatCo",
        "category": "outerwear",
        "price": 219.99,
        "image_url": "https://images.unsplash.com/photo-1544923246-77307dd654cb?auto=format&fit=crop&w=800&q=80",
        "description": "800-fill goose down, oyster white, ankle-length cocoon silhouette, concealed zip and button placket, stand collar, side slit pockets. Extremely warm for extreme cold.",
        "rating": 4.5,
        "review_count": 10,
        "attributes": {"color": "oyster white", "material": "goose down + ripstop nylon"},
    },
]

PRODUCT_MAP = {p["asin"]: p for p in MOCK_PRODUCTS}


# ── Pydantic Models ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    asin: str
    question: str


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/products")
async def get_products():
    # TODO: replace with Qdrant query — scroll products_v2 collection, return all payloads
    return [
        {
            "asin": p["asin"],
            "name": p["name"],
            "brand": p["brand"],
            "price": p["price"],
            "image_url": p["image_url"],
            "category": p["category"],
            "rating": p["rating"],
            "review_count": p["review_count"],
        }
        for p in MOCK_PRODUCTS
    ]


@app.get("/api/products/{asin}")
async def get_product(asin: str):
    # TODO: replace with Qdrant query — filter products_v2 by asin field
    product = PRODUCT_MAP.get(asin)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/api/query")
async def query(req: QueryRequest):
    # TODO: replace with real agent pipeline:
    #   from agent.tool_selector import select_tools
    #   from agent.executor import execute_tools
    #   from agent.conflict_detector import detect_conflicts, format_conflicts
    #   from agent.context_assembler import assemble_context
    #   from frontend.app_v2 import generate_llm_answer
    #
    #   1. reasoning, tool_calls = select_tools(req.question, req.asin)
    #   2. tool_results = execute_tools(tool_calls)
    #   3. conflicts = detect_conflicts(tool_results)
    #   4. context = assemble_context(req.question, req.asin, product_info, tool_results)
    #   5. answer = generate_llm_answer(context, req.question)

    # Simulate real LLM + Qdrant processing time
    await asyncio.sleep(1.2)

    product = PRODUCT_MAP.get(req.asin, {})
    product_name = product.get("name", req.asin)
    material = product.get("attributes", {}).get("material", "unknown material")

    return {
        "answer": (
            f"[Demo] 关于「{product_name}」的问题：{req.question}\n\n"
            "这是模拟回答。接入真实 API Key 后，此处将由 LLM 基于 Qdrant 检索到的评价、"
            "材质知识和视觉描述生成完整回答。"
        ),
        "tool_selection": {
            "reasoning": (
                f"用户询问关于 {product_name} 的问题，涉及使用体验。"
                "优先检索真实评价，同时查询材质知识库以补充专业信息。"
            ),
            "tools": ["semantic_review_search", "knowledge_retrieval"],
        },
        "tool_results": [
            {
                "tool_name": "semantic_review_search",
                "duration_ms": 312,
                "relevance_score": 0.87,
                "result_summary": "找到 5 条相关评价",
            },
            {
                "tool_name": "knowledge_retrieval",
                "duration_ms": 198,
                "relevance_score": 0.74,
                "result_summary": f"找到 {material} 相关知识 2 条",
            },
        ],
        "context_assembly": (
            f"# 商品信息\n名称: {product_name}\n材质: {material}\n\n"
            "# 相关评价\n"
            "- 评价1: 非常保暖，零下8度穿着舒适...\n"
            "- 评价2: 材质摸起来很高级，不起球...\n"
            "- 评价3: 尺码偏小，建议买大一号...\n\n"
            "# 知识库\n"
            f"- {material} 特性：保暖性强，适合寒冷天气...\n\n"
            f"# 用户问题\n{req.question}"
        ),
        "conflict_detection": {
            "has_conflict": False,
            "details": "知识库与用户评价之间未发现明显矛盾。",
        },
    }


@app.get("/api/tools")
async def get_tools():
    # TODO: replace with agent.tools.list_tools() once agent is wired up
    return [
        {"name": "product_lookup", "description": "在 Qdrant products_v2 中进行语义商品搜索"},
        {"name": "review_search", "description": "在 reviews_v2 中语义检索用户评价"},
        {"name": "knowledge_search", "description": "在 knowledge_v2 中检索材质与面料专业知识"},
        {"name": "visual_search", "description": "在 visual_semantic_v2 中检索商品视觉描述"},
        {"name": "conflict_detector", "description": "检测知识库与用户评价之间的矛盾"},
    ]
