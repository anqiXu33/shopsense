# ShopSense Qdrant-First 工具系统架构设计

## TL;DR

> **目标**: 构建基于 Qdrant 的 LLM 工具调用系统，支持语义搜索、评价挖掘、知识检索、视觉分析等 7 个核心工具  
> **核心创新**: 所有数据存 Qdrant，利用 Hybrid Search、Discovery、Facet 等高级特性  
> **调用模式**: LLM Function Calling → 并行执行 → 动态上下文组装 → 生成回答  
> **Token 策略**: 基于工具结果的相关性分数动态分配上下文预算

---

## 1. 系统架构

### 1.1 整体流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户查询                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: LLM Intent + Tool Selection (Function Calling)             │
│  ─────────────────────────────────────────────────────────────     │
│  System: "你是购物助手，分析用户需求，选择合适的工具"                 │
│  Input: 用户查询 + 可选上下文                                        │
│  Output: {reasoning, tool_calls: [...]}                              │
│                                                                     │
│  关键: LLM 根据查询语义决定调用哪些工具，不需要预定义计划             │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: Parallel Tool Execution                                    │
│  ─────────────────────────────────────────────────────────────     │
│  所有工具独立执行，向 Qdrant 发起并行查询                             │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ semantic_    │ │ semantic_    │ │ knowledge_   │                │
│  │ product_     │ │ review_      │ │ retrieval    │   ...          │
│  │ search       │ │ search       │ │              │                │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘                │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│                   Qdrant Cloud/Local                                │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: Dynamic Context Assembly                                   │
│  ─────────────────────────────────────────────────────────────     │
│  1. 收集所有工具结果                                                 │
│  2. 按相关性分数(relevance score)排序                                │
│  3. 动态分配 Token 预算（高分多分配）                                │
│  4. 冲突检测：不同来源信息矛盾时标记                                 │
│  5. 组装最终 Prompt                                                  │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4: Answer Generation                                          │
│  ─────────────────────────────────────────────────────────────     │
│  LLM 生成回答 + 引用来源                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Qdrant Collections 设计

```
┌─────────────────────────────────────────────────────────────────────┐
│  Collection: products                                               │
│  ─────────────────────────────────────────────────────────────     │
│  Vector: 1024-dim (dense) + sparse (BM25)                          │
│  Payload:                                                           │
│    - asin: string (keyword index)                                  │
│    - name: string                                                  │
│    - brand: string (keyword index)                                 │
│    - category: string (keyword index)                              │
│    - price: number (float index)                                   │
│    - description: string                                           │
│    - attributes: {color, material, style, ...}                     │
│    - image_url: string                                             │
│    - rating: float                                                 │
│    - review_count: int                                             │
│  Purpose: 商品语义搜索、属性过滤                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Collection: reviews                                                │
│  ─────────────────────────────────────────────────────────────     │
│  Vector: 1024-dim (dense)                                          │
│  Payload:                                                           │
│    - asin: string (keyword index)                                  │
│    - text: string                                                  │
│    - rating: int (integer index)                                   │
│    - sentiment: string [positive/negative/neutral] (keyword)       │
│    - reviewer_height: int (integer index)                          │
│    - reviewer_weight: int                                          │
│    - helpful_votes: int                                            │
│    - verified_purchase: bool                                       │
│  Purpose: 评价语义检索、多维度过滤                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Collection: knowledge                                              │
│  ─────────────────────────────────────────────────────────────     │
│  Vector: 1024-dim (dense)                                          │
│  Payload:                                                           │
│    - topic: string (keyword index)                                 │
│    - material: string (keyword index)                              │
│    - category: string                                              │
│    - content: string                                               │
│    - source: string                                                │
│  Purpose: 材料知识、尺码标准、保养建议                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Collection: visual_semantic                                        │
│  ─────────────────────────────────────────────────────────────     │
│  Vector: 1024-dim (dense)                                          │
│  Payload:                                                           │
│    - asin: string (keyword index)                                  │
│    - image_type: string [main/detail]                              │
│    - description: string (VLM 预生成)                              │
│    - attributes: {                                                  │
│        color: string,                                               │
│        style: string,                                               │
│        texture: string,                                             │
│        fit: string                                                  │
│      }                                                              │
│  Purpose: 视觉语义搜索（无需实时调用 VLM）                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Collection: qa_pairs (可选)                                        │
│  ─────────────────────────────────────────────────────────────     │
│  Vector: 1024-dim (dense)                                          │
│  Payload:                                                           │
│    - question: string                                              │
│    - answer: string                                                │
│    - asin: string                                                  │
│    - helpful_count: int                                            │
│  Purpose: 相似问题检索、FAQ 复用                                    │
└─────────────────────────────────────────────────────────────────────┘
```


---

## 2. 工具详细设计

### 2.1 Tool 1: semantic_product_search

**功能**: 基于语义搜索商品，支持属性过滤

**何时调用**:
- 用户想找某类商品但未指定具体 ASIN
- 需要根据描述推荐相似商品
- "有没有保暖的羽绒服？"

**Schema**:
```json
{
  "name": "semantic_product_search",
  "description": "基于语义搜索商品。使用 Qdrant 的 hybrid search（稠密向量语义 + 稀疏向量关键词）查找相关商品。支持按价格、品牌、品类过滤。当用户想找某类商品、或需要推荐相似商品时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索查询，如'保暖的羽绒服'、'适合敏感肌的毛衣'"
      },
      "filters": {
        "type": "object",
        "description": "可选过滤条件",
        "properties": {
          "price_min": {"type": "number", "description": "最低价格"},
          "price_max": {"type": "number", "description": "最高价格"},
          "brands": {"type": "array", "items": {"type": "string"}, "description": "品牌白名单"},
          "category": {"type": "string", "description": "品类"},
          "rating_min": {"type": "number", "description": "最低评分"}
        }
      },
      "top_k": {
        "type": "integer",
        "default": 5,
        "description": "返回商品数量"
      }
    },
    "required": ["query"]
  }
}
```

**Qdrant 实现**:
```python
def semantic_product_search(query: str, filters: dict = None, top_k: int = 5):
    # 1. 生成稠密向量
    dense_vector = embed_dense(query)
    
    # 2. 构建 payload filter
    must_conditions = []
    if filters:
        if filters.get("price_min") or filters.get("price_max"):
            must_conditions.append(
                FieldCondition(
                    key="price",
                    range=Range(
                        gte=filters.get("price_min"),
                        lte=filters.get("price_max")
                    )
                )
            )
        if filters.get("brands"):
            must_conditions.append(
                FieldCondition(
                    key="brand",
                    match=MatchAny(any=filters["brands"])
                )
            )
        if filters.get("category"):
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=filters["category"]))
            )
    
    # 3. Query
    results = client.query_points(
        collection_name="products",
        query=dense_vector,
        query_filter=Filter(must=must_conditions) if must_conditions else None,
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )
    
    return [{
        "asin": r.payload["asin"],
        "name": r.payload["name"],
        "brand": r.payload["brand"],
        "price": r.payload["price"],
        "rating": r.payload["rating"],
        "description": r.payload["description"][:200] + "...",
        "relevance_score": r.score,
        "image_url": r.payload["image_url"]
    } for r in results.points]
```

**返回值**:
```json
[
  {
    "asin": "B001",
    "name": "Alpine Duck Down Jacket",
    "brand": "NorthPeak",
    "price": 129.99,
    "rating": 4.2,
    "description": "Duck down fill 450g, deep navy blue color...",
    "relevance_score": 0.89,
    "image_url": "https://..."
  }
]
```


---

### 2.2 Tool 2: semantic_review_search (核心工具)

**功能**: 基于语义检索用户评价，支持多维度过滤和分组

**何时调用**:
- 用户询问具体使用体验
- 需要筛选特定人群的反馈（如相同身高）
- "保暖吗？"、"尺码准吗？"、"敏感肌能用吗？"

**Schema**:
```json
{
  "name": "semantic_review_search",
  "description": "基于语义搜索用户评价。使用 Qdrant 向量搜索找相关反馈，支持按评分、身高、情感等过滤。可以只搜特定商品，也可以跨商品搜索。当用户询问具体使用体验、需要真实买家反馈时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索主题，如'保暖性怎么样'、'尺码偏小'、'过敏反应'"
      },
      "asin": {
        "type": "string",
        "description": "指定商品 ASIN，可选。不指定则搜索所有商品"
      },
      "filters": {
        "type": "object",
        "description": "过滤条件",
        "properties": {
          "sentiment": {
            "type": "string",
            "enum": ["positive", "negative", "neutral", "all"],
            "default": "all"
          },
          "rating_min": {"type": "integer", "description": "最低评分 1-5"},
          "rating_max": {"type": "integer", "description": "最高评分 1-5"},
          "reviewer_height_min": {"type": "integer", "description": "评价者最小身高(cm)"},
          "reviewer_height_max": {"type": "integer", "description": "评价者最大身高(cm)"},
          "verified_only": {"type": "boolean", "default": true, "description": "只看verified purchase"}
        }
      },
      "top_k": {
        "type": "integer",
        "default": 5,
        "description": "返回评价数量"
      },
      "group_by_asin": {
        "type": "boolean",
        "default": false,
        "description": "是否按 ASIN 分组（对比场景）"
      }
    },
    "required": ["query"]
  }
}
```

**Qdrant 实现**:
```python
def semantic_review_search(
    query: str,
    asin: str = None,
    filters: dict = None,
    top_k: int = 5,
    group_by_asin: bool = False
):
    vector = embed_dense(query)
    
    # 构建过滤条件
    must_conditions = []
    if asin:
        must_conditions.append(
            FieldCondition(key="asin", match=MatchValue(value=asin))
        )
    
    if filters:
        if filters.get("sentiment") and filters["sentiment"] != "all":
            must_conditions.append(
                FieldCondition(key="sentiment", match=MatchValue(value=filters["sentiment"]))
            )
        if filters.get("rating_min") or filters.get("rating_max"):
            must_conditions.append(
                FieldCondition(
                    key="rating",
                    range=Range(
                        gte=filters.get("rating_min"),
                        lte=filters.get("rating_max")
                    )
                )
            )
        if filters.get("reviewer_height_min") or filters.get("reviewer_height_max"):
            must_conditions.append(
                FieldCondition(
                    key="reviewer_height",
                    range=Range(
                        gte=filters.get("reviewer_height_min"),
                        lte=filters.get("reviewer_height_max")
                    )
                )
            )
        if filters.get("verified_only", True):
            must_conditions.append(
                FieldCondition(key="verified_purchase", match=MatchValue(value=True))
            )
    
    if group_by_asin:
        # 使用 grouping (Qdrant 1.8+)
        results = client.query_points_groups(
            collection_name="reviews",
            query=vector,
            query_filter=Filter(must=must_conditions) if must_conditions else None,
            group_by="asin",
            limit=top_k,
            group_size=3,
            with_payload=True
        )
        return {
            "groups": [
                {
                    "asin": g.key,
                    "reviews": [{
                        "text": p.payload["text"],
                        "rating": p.payload["rating"],
                        "sentiment": p.payload["sentiment"],
                        "reviewer_height": p.payload.get("reviewer_height"),
                        "relevance_score": p.score
                    } for p in g.hits]
                }
                for g in results.groups
            ]
        }
    else:
        results = client.query_points(
            collection_name="reviews",
            query=vector,
            query_filter=Filter(must=must_conditions) if must_conditions else None,
            limit=top_k,
            with_payload=True
        )
        
        return [{
            "asin": r.payload["asin"],
            "text": r.payload["text"],
            "rating": r.payload["rating"],
            "sentiment": r.payload["sentiment"],
            "reviewer_height": r.payload.get("reviewer_height"),
            "helpful_votes": r.payload.get("helpful_votes"),
            "relevance_score": r.score
        } for r in results.points]
```


---

### 2.3 Tool 3: knowledge_retrieval

**功能**: 检索专业知识库

**何时调用**:
- 需要材料特性、尺码标准等专业背景
- "650FP羽绒能抗多少度？"、"羊毛会过敏吗？"

**Schema**:
```json
{
  "name": "knowledge_retrieval",
  "description": "检索专业知识库。查询材料特性、保暖性、皮肤兼容性、尺码标准、保养方法等专业信息。当需要专业背景知识回答材质、保养、敏感肌等问题时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "查询主题，如'650FP羽绒保暖性'、'羊毛过敏'、'尺码换算'"
      },
      "material": {
        "type": "string",
        "description": "具体材料名称，可选"
      },
      "topic": {
        "type": "string",
        "enum": ["material", "warmth", "skin", "sizing", "care", "general"],
        "description": "知识类别"
      },
      "top_k": {
        "type": "integer",
        "default": 3,
        "description": "返回知识条目数量"
      }
    },
    "required": ["query"]
  }
}
```

**Qdrant 实现**:
```python
def knowledge_retrieval(query: str, material: str = None, topic: str = None, top_k: int = 3):
    vector = embed_dense(query)
    
    must_conditions = []
    if material:
        must_conditions.append(
            FieldCondition(key="material", match=MatchValue(value=material))
        )
    if topic and topic != "general":
        must_conditions.append(
            FieldCondition(key="topic", match=MatchValue(value=topic))
        )
    
    results = client.query_points(
        collection_name="knowledge",
        query=vector,
        query_filter=Filter(must=must_conditions) if must_conditions else None,
        limit=top_k,
        with_payload=True
    )
    
    return [{
        "material": r.payload["material"],
        "topic": r.payload["topic"],
        "content": r.payload["content"],
        "properties": r.payload.get("properties", ""),
        "skin_notes": r.payload.get("skin_notes", ""),
        "warmth_range": r.payload.get("warmth_range", ""),
        "source": r.payload.get("source", ""),
        "relevance_score": r.score
    } for r in results.points]
```

---

### 2.4 Tool 4: visual_semantic_search

**功能**: 基于预生成的视觉描述进行语义搜索

**何时调用**:
- 用户询问颜色、款式、版型等视觉属性
- "什么颜色？"、"长什么样？"、"修身还是宽松？"

**Schema**:
```json
{
  "name": "visual_semantic_search",
  "description": "基于预生成的视觉描述进行语义搜索。不需要实时调用 VLM，直接搜索已存储的视觉语义向量。当用户询问颜色、款式、版型等视觉属性时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "asin": {
        "type": "string",
        "description": "商品 ASIN"
      },
      "query": {
        "type": "string",
        "description": "视觉查询，如'颜色'、'版型'、'细节'、'深蓝色'"
      },
      "top_k": {
        "type": "integer",
        "default": 3,
        "description": "返回结果数量"
      }
    },
    "required": ["asin", "query"]
  }
}
```

**Qdrant 实现**:
```python
def visual_semantic_search(asin: str, query: str, top_k: int = 3):
    vector = embed_dense(query)
    
    results = client.query_points(
        collection_name="visual_semantic",
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="asin", match=MatchValue(value=asin))]
        ),
        limit=top_k,
        with_payload=True
    )
    
    return [{
        "asin": r.payload["asin"],
        "image_type": r.payload["image_type"],
        "description": r.payload["description"],
        "attributes": r.payload.get("attributes", {}),
        "relevance_score": r.score
    } for r in results.points]
```


---

### 2.5 Tool 5: discovery_similar

**功能**: 发现相似或对比商品/评价 (Qdrant Discovery API)

**何时调用**:
- "找类似这件但更便宜的"、"和A比怎么样？"
- 需要复杂语义对比场景

**Schema**:
```json
{
  "name": "discovery_similar",
  "description": "使用 Qdrant Discovery API 找与目标相似或相反的商品/评价。支持'像A但不像B'的复杂查询。当用户想要类似商品、或需要对比不同选项时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "target_asin": {
        "type": "string",
        "description": "目标商品 ASIN"
      },
      "positive_examples": {
        "type": "array",
        "items": {"type": "string"},
        "description": "正面示例 ASIN 列表（希望相似的）"
      },
      "negative_examples": {
        "type": "array",
        "items": {"type": "string"},
        "description": "负面示例 ASIN 列表（希望不同的）"
      },
      "context": {
        "type": "string",
        "description": "对比维度，如'保暖性'、'价格'、'版型'"
      },
      "top_k": {
        "type": "integer",
        "default": 5,
        "description": "返回结果数量"
      }
    },
    "required": ["target_asin"]
  }
}
```

**Qdrant 实现**:
```python
def discovery_similar(
    target_asin: str,
    positive_examples: list = None,
    negative_examples: list = None,
    context: str = None,
    top_k: int = 5
):
    # 获取目标向量
    target_point = client.retrieve(
        collection_name="products",
        ids=[target_asin],
        with_vectors=True
    )[0]
    target_vector = target_point.vector
    
    # 构建上下文对
    context_pairs = []
    if context:
        # 例如 context="保暖性": 构建 positive="很保暖", negative="不保暖"
        context_pairs.append({
            "positive": embed_dense(f"{context} 好 优秀"),
            "negative": embed_dense(f"{context} 差 不好")
        })
    
    results = client.discover(
        collection_name="products",
        target=target_vector,
        context=context_pairs if context_pairs else None,
        limit=top_k,
        with_payload=True
    )
    
    return [{
        "asin": r.payload["asin"],
        "name": r.payload["name"],
        "brand": r.payload["brand"],
        "price": r.payload["price"],
        "similarity_score": r.score
    } for r in results]
```

---

### 2.6 Tool 6: facet_insights

**功能**: 分面统计洞察 (Qdrant Facet API)

**何时调用**:
- 快速了解评价分布
- "各尺码的评价怎么样？"、"好评都说什么？"

**Schema**:
```json
{
  "name": "facet_insights",
  "description": "使用 Qdrant Facet API 对评价进行分面统计。快速了解各评分、尺码、情感的评价分布。当需要统计洞察、了解整体评价趋势时使用。",
  "parameters": {
    "type": "object",
    "properties": {
      "asin": {
        "type": "string",
        "description": "商品 ASIN"
      },
      "facet_key": {
        "type": "string",
        "enum": ["rating", "sentiment", "size"],
        "description": "分面维度"
      },
      "query": {
        "type": "string",
        "description": "可选过滤查询，如'尺码'只统计提到尺码的评价"
      },
      "limit": {
        "type": "integer",
        "default": 10,
        "description": "返回分面值数量"
      }
    },
    "required": ["asin", "facet_key"]
  }
}
```

**Qdrant 实现**:
```python
def facet_insights(asin: str, facet_key: str, query: str = None, limit: int = 10):
    # 可选：先用查询过滤
    filter_conditions = [FieldCondition(key="asin", match=MatchValue(value=asin))]
    
    if query:
        # 语义过滤：先找相关评价，再分面
        vector = embed_dense(query)
        # 先搜索，再对结果分面（简化实现）
        search_results = client.query_points(
            collection_name="reviews",
            query=vector,
            query_filter=Filter(must=filter_conditions),
            limit=100,
            with_payload=True
        )
        # 手动统计
        from collections import Counter
        values = [r.payload.get(facet_key) for r in search_results.points if r.payload.get(facet_key)]
        counter = Counter(values)
        return {
            "facet_key": facet_key,
            "query": query,
            "distribution": dict(counter.most_common(limit))
        }
    else:
        # 使用 Facet API (Qdrant 1.8+)
        results = client.facet(
            collection_name="reviews",
            key=facet_key,
            facet_filter=Filter(must=filter_conditions),
            limit=limit
        )
        return {
            "facet_key": facet_key,
            "distribution": {item.key: item.count for item in results}
        }
```


---

### 2.7 Tool 7: recommend_by_example

**功能**: 基于正负例推荐商品 (Qdrant Recommend API)

**何时调用**:
- 用户说"喜欢A和B，不喜欢C"
- 需要个性化推荐

**Schema**:
```json
{
  "name": "recommend_by_example",
  "description": "使用 Qdrant Recommend API 基于正/负例推荐商品。当用户表达偏好（'我喜欢A和B，不喜欢C'）时，推荐相似商品。",
  "parameters": {
    "type": "object",
    "properties": {
      "positive_asins": {
        "type": "array",
        "items": {"type": "string"},
        "description": "喜欢的商品 ASIN 列表"
      },
      "negative_asins": {
        "type": "array",
        "items": {"type": "string"},
        "description": "不喜欢的商品 ASIN 列表"
      },
      "limit": {
        "type": "integer",
        "default": 5,
        "description": "推荐数量"
      }
    },
    "required": ["positive_asins"]
  }
}
```

**Qdrant 实现**:
```python
def recommend_by_example(
    positive_asins: list,
    negative_asins: list = None,
    limit: int = 5
):
    results = client.recommend(
        collection_name="products",
        positive=positive_asins,
        negative=negative_asins or [],
        limit=limit,
        with_payload=True
    )
    
    return [{
        "asin": r.payload["asin"],
        "name": r.payload["name"],
        "brand": r.payload["brand"],
        "price": r.payload["price"],
        "rating": r.payload["rating"],
        "recommendation_score": r.score
    } for r in results]
```

---

## 3. 动态 Token 权重策略

### 3.1 核心原则

不再基于意图类型预设权重，而是基于**工具返回结果的相关性分数**动态分配：

```python
# 旧策略（废弃）
TOKEN_BUDGETS = {
    "warmth_inquiry": {"knowledge": 0.50, "reviews": 0.40, "sizing": 0.10},
    # ...
}

# 新策略（动态）
# 1. 收集所有工具结果及其 relevance_score
# 2. 按 score 排序
# 3. 高分结果获得更多 token 预算
# 4. 保持信息多样性（不全是同一类型）
```

### 3.2 分配算法

```python
def allocate_token_budget(tool_results: dict, max_tokens: int = 2000) -> dict:
    """
    动态分配 Token 预算
    
    Args:
        tool_results: {tool_name: [results_with_score]}
        max_tokens: 总预算
    
    Returns:
        {tool_name: allocated_tokens}
    """
    # Step 1: 收集所有结果及其分数
    all_results = []
    for tool_name, results in tool_results.items():
        for r in results:
            all_results.append({
                "tool": tool_name,
                "result": r,
                "score": r.get("relevance_score", 0.5),
                "priority": get_tool_priority(tool_name)  # 基础优先级
            })
    
    # Step 2: 计算加权分数（考虑基础优先级）
    for r in all_results:
        r["weighted_score"] = r["score"] * r["priority"]
    
    # Step 3: 按加权分数排序
    all_results.sort(key=lambda x: x["weighted_score"], reverse=True)
    
    # Step 4: 分配预算（按分数比例）
    total_score = sum(r["weighted_score"] for r in all_results)
    allocations = {}
    
    reserved = 500  # 预留 500 tokens 给基础信息（产品名、系统提示等）
    available = max_tokens - reserved
    
    for r in all_results:
        ratio = r["weighted_score"] / total_score if total_score > 0 else 0
        allocations[r["tool"]] = allocations.get(r["tool"], 0) + int(available * ratio)
    
    return allocations


def get_tool_priority(tool_name: str) -> float:
    """工具基础优先级（可调）"""
    priorities = {
        "semantic_review_search": 1.2,   # 评价最重要
        "visual_semantic_search": 1.1,   # 视觉信息
        "knowledge_retrieval": 1.0,      # 知识中等
        "semantic_product_search": 0.9,  # 商品信息
        "discovery_similar": 0.8,        # 发现
        "facet_insights": 0.7,           # 统计
        "recommend_by_example": 0.8,     # 推荐
    }
    return priorities.get(tool_name, 1.0)
```

### 3.3 上下文截断策略

```python
def assemble_context_with_budget(tool_results: dict, budget: dict) -> str:
    """
    根据预算组装上下文
    """
    sections = []
    
    # 必含部分
    sections.append(_system_prompt())
    sections.append(_product_basic_info())
    
    # 按预算分配组装各工具结果
    for tool_name, allocated_tokens in sorted(budget.items(), key=lambda x: -x[1]):
        if tool_name not in tool_results:
            continue
        
        results = tool_results[tool_name]
        max_chars = allocated_tokens * 4  # 约 1 token = 4 chars
        
        content = format_tool_results(tool_name, results)
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        
        sections.append(f"[{tool_name.upper()}]\n{content}")
    
    return "\n\n".join(sections)
```


---

## 4. 端到端调用流程

### 4.1 完整流程示例

**场景**: 用户问"这件羽绒服保暖吗？我170cm敏感肌"

```python
# ========== Step 1: LLM Tool Selection ==========
system_prompt = """
你是 ShopSense 购物助手。分析用户查询，选择合适的工具获取信息。

可用工具:
1. semantic_product_search - 搜索商品
2. semantic_review_search - 搜索评价
3. knowledge_retrieval - 检索知识
4. visual_semantic_search - 视觉语义搜索
5. discovery_similar - 发现相似商品
6. facet_insights - 分面统计
7. recommend_by_example - 基于示例推荐

规则:
- 选择最相关的 2-4 个工具
- 优先使用 semantic_review_search 获取真实反馈
- 涉及材质/保暖性时调用 knowledge_retrieval
- 每个工具调用必须包含完整参数
"""

user_query = "这件羽绒服保暖吗？我170cm敏感肌"
current_asin = "B001"  # 当前商品

# LLM 返回:
llm_response = {
    "reasoning": "用户询问保暖性和敏感肌适用性。需要: 1) 搜索相关评价; 2) 查询羽绒保暖知识; 3) 查询敏感肌相关知识",
    "tool_calls": [
        {
            "name": "semantic_review_search",
            "arguments": {
                "asin": "B001",
                "query": "保暖性怎么样 敏感肌 过敏",
                "filters": {
                    "reviewer_height_min": 165,
                    "reviewer_height_max": 175
                },
                "top_k": 5
            }
        },
        {
            "name": "knowledge_retrieval",
            "arguments": {
                "query": "鸭绒羽绒服保暖性 450g充绒量",
                "material": "down",
                "topic": "warmth",
                "top_k": 3
            }
        },
        {
            "name": "knowledge_retrieval",
            "arguments": {
                "query": "羽绒服敏感肌 过敏 皮肤",
                "material": "down",
                "topic": "skin",
                "top_k": 3
            }
        }
    ]
}

# ========== Step 2: Parallel Tool Execution ==========
import asyncio

async def execute_tools(tool_calls):
    tasks = []
    for call in tool_calls:
        tool_fn = TOOL_REGISTRY[call["name"]]
        tasks.append(tool_fn(**call["arguments"]))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 组装结果
    tool_results = {}
    for call, result in zip(tool_calls, results):
        if isinstance(result, Exception):
            print(f"Tool {call['name']} failed: {result}")
            tool_results[call["name"]] = []
        else:
            tool_results[call["name"]] = result
    
    return tool_results

tool_results = await execute_tools(llm_response["tool_calls"])

# 结果示例:
# {
#     "semantic_review_search": [
#         {"text": "在-8度穿很暖和", "rating": 5, "relevance_score": 0.92},
#         {"text": "-15度不够暖", "rating": 3, "relevance_score": 0.88},
#         {"text": "敏感肌可用，没过敏", "rating": 5, "relevance_score": 0.85}
#     ],
#     "knowledge_retrieval": [
#         {"content": "450g鸭绒适合-5到-10度", "relevance_score": 0.95},
#         {"content": "羽绒外层聚酯纤维，不直接接触皮肤", "relevance_score": 0.90}
#     ]
# }

# ========== Step 3: Dynamic Context Assembly ==========
budget = allocate_token_budget(tool_results, max_tokens=2000)
# 示例: {
#     "semantic_review_search": 900,    # 高分，多分配
#     "knowledge_retrieval": 600        # 次高分
# }

context = assemble_context_with_budget(tool_results, budget)

# 组装后的上下文:
# """
# [SYSTEM] 你是 ShopSense 购物助手...
#
# [PRODUCT] Alpine Duck Down Jacket | Brand: NorthPeak | Price: $129.99
#
# [SEMANTIC_REVIEW_SEARCH]
# ✓ "在-8度北海道穿了一整天，很暖和" (评分: 5, 相关度: 0.92)
# ✓ "-15度不够暖，只适合-5到-10度" (评分: 3, 相关度: 0.88)
# ✓ "敏感肌可用，没出现过敏反应" (评分: 5, 相关度: 0.85)
#
# [KNOWLEDGE_RETRIEVAL]
# - 450g鸭绒适合-5到-10度环境，650蓬松度
# - 羽绒服外层通常为聚酯纤维，不直接接触皮肤，敏感肌通常可接受
#
# [USER CONTEXT]
# 身高: 170cm, 皮肤状况: 敏感
#
# 请根据以上信息回答用户问题：这件羽绒服保暖吗？
# """

# ========== Step 4: Answer Generation ==========
answer = generate_answer(context, user_query)
# "根据评价和专业知识，这件羽绒服填充450g鸭绒，适合-5到-10度环境。
# 有用户评价在-8度北海道穿着舒适，但也有用户觉得-15度不够暖。
# 对于敏感肌，羽绒服外层是聚酯纤维，不直接接触皮肤，一般不会引起过敏。
# 如果你是极寒地区使用，可能需要考虑更厚款。"
```

### 4.2 工具调用决策矩阵

| 用户意图 | 推荐工具组合 |
|---------|-------------|
| "这件多少钱？" | `semantic_product_search` |
| "什么颜色？长什么样？" | `visual_semantic_search` |
| "保暖吗？" | `semantic_review_search` + `knowledge_retrieval` |
| "我170cm穿什么码？" | `semantic_review_search` (筛选身高) + `facet_insights` |
| "敏感肌能用吗？" | `knowledge_retrieval` (material+skin) + `semantic_review_search` (过敏) |
| "和另一件比怎么样？" | `discovery_similar` 或并行查询两个 ASIN 的 `semantic_review_search` |
| "有没有类似的但更便宜的？" | `discovery_similar` + `semantic_product_search` (价格过滤) |
| "这个牌子靠谱吗？" | `semantic_review_search` (跨商品) + `facet_insights` |


---

## 5. 数据导入 (Ingestion)

### 5.1 Collection 创建脚本

```python
# scripts/setup_collections.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

client = QdrantClient(url="http://localhost:6333")

# Collection: products
client.create_collection(
    collection_name="products",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
client.create_payload_index("products", "asin", PayloadSchemaType.KEYWORD)
client.create_payload_index("products", "brand", PayloadSchemaType.KEYWORD)
client.create_payload_index("products", "category", PayloadSchemaType.KEYWORD)
client.create_payload_index("products", "price", PayloadSchemaType.FLOAT)

# Collection: reviews
client.create_collection(
    collection_name="reviews",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
client.create_payload_index("reviews", "asin", PayloadSchemaType.KEYWORD)
client.create_payload_index("reviews", "rating", PayloadSchemaType.INTEGER)
client.create_payload_index("reviews", "sentiment", PayloadSchemaType.KEYWORD)
client.create_payload_index("reviews", "reviewer_height", PayloadSchemaType.INTEGER)

# Collection: knowledge
client.create_collection(
    collection_name="knowledge",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
client.create_payload_index("knowledge", "topic", PayloadSchemaType.KEYWORD)
client.create_payload_index("knowledge", "material", PayloadSchemaType.KEYWORD)

# Collection: visual_semantic
client.create_collection(
    collection_name="visual_semantic",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)
client.create_payload_index("visual_semantic", "asin", PayloadSchemaType.KEYWORD)
```

### 5.2 数据导入流程

```python
# scripts/ingest_v2.py
import json
from tqdm import tqdm
from qdrant_client.models import PointStruct

def ingest_products(products_data):
    """导入商品到 products collection"""
    points = []
    for p in tqdm(products_data, desc="Products"):
        # 生成描述文本的 embedding
        text = f"{p['name']}: {p['description']}"
        vector = embed(text)
        
        points.append(PointStruct(
            id=p['asin'],
            vector=vector,
            payload={
                "asin": p['asin'],
                "name": p['name'],
                "brand": p['brand'],
                "category": p['category'],
                "price": p['price'],
                "description": p['description'],
                "attributes": p.get('attributes', {}),
                "image_url": p['image_url'],
                "rating": p.get('rating', 0),
                "review_count": p.get('review_count', 0)
            }
        ))
    
    client.upsert("products", points)
    print(f"Ingested {len(points)} products")


def ingest_reviews(reviews_data):
    """导入评价到 reviews collection"""
    points = []
    idx = 0
    for r in tqdm(reviews_data, desc="Reviews"):
        vector = embed(r['text'])
        
        points.append(PointStruct(
            id=idx,
            vector=vector,
            payload={
                "asin": r['asin'],
                "text": r['text'],
                "rating": r['rating'],
                "sentiment": r.get('sentiment', 'neutral'),
                "reviewer_height": r.get('reviewer_height'),
                "reviewer_weight": r.get('reviewer_weight'),
                "helpful_votes": r.get('helpful_votes', 0),
                "verified_purchase": r.get('verified_purchase', False)
            }
        ))
        idx += 1
    
    client.upsert("reviews", points)
    print(f"Ingested {len(points)} reviews")


def ingest_visual_semantic(products_data):
    """预生成视觉描述并导入 visual_semantic"""
    points = []
    idx = 0
    for p in tqdm(products_data, desc="Visual"):
        if p.get('image_url') and p['image_url'] != 'placeholder':
            # 调用 VLM 生成描述
            description = generate_visual_description(p['image_url'])
            vector = embed(description)
            
            points.append(PointStruct(
                id=idx,
                vector=vector,
                payload={
                    "asin": p['asin'],
                    "image_type": "main",
                    "description": description,
                    "attributes": extract_visual_attributes(description)
                }
            ))
            idx += 1
    
    client.upsert("visual_semantic", points)
    print(f"Ingested {len(points)} visual descriptions")
```

---

## 6. 代码结构建议

```
shopsense/
├── config/
│   └── settings.py              # Qdrant 配置、模型配置
├── data/
│   └── sample_products.json     # 商品数据
├── agent/
│   ├── __init__.py
│   ├── agent.py                 # 主 Agent 循环
│   ├── tool_selector.py         # LLM 工具选择
│   ├── context_assembler.py     # 动态上下文组装
│   └── tools/                   # 工具实现
│       ├── __init__.py
│       ├── base.py              # 工具基类
│       ├── product_search.py    # semantic_product_search
│       ├── review_search.py     # semantic_review_search
│       ├── knowledge.py         # knowledge_retrieval
│       ├── visual.py            # visual_semantic_search
│       ├── discovery.py         # discovery_similar
│       ├── facet.py             # facet_insights
│       └── recommend.py         # recommend_by_example
├── qdrant_client/
│   ├── __init__.py
│   ├── client.py                # Qdrant 客户端封装
│   └── embeddings.py            # Embedding 生成
├── scripts/
│   ├── setup_collections.py     # 创建 collections
│   ├── ingest_v2.py             # 数据导入
│   └── build_knowledge.py       # 构建知识库
└── frontend/
    └── app.py                   # Gradio UI
```

---

## 7. 关键技术决策

### 7.1 为什么选择 Function Calling 而不是 ReAct?

| 方案 | 优点 | 缺点 | 选择 |
|-----|-----|-----|-----|
| Function Calling | 结构化输出，解析可靠，延迟低 | 需要模型支持 | ✅ 选用 |
| ReAct | 更灵活，可解释性强 | 需要解析文本，易出错 | 不选用 |

### 7.2 为什么视觉描述预生成而不是实时调用 VLM?

- **延迟**: 实时调用 VLM 每次 1-3s，用户体验差
- **成本**: 预生成一次性成本，运行时零成本
- **一致性**: 预生成描述质量可控

### 7.3 Token 动态分配 vs 固定预算

| 方案 | 优点 | 缺点 | 选择 |
|-----|-----|-----|-----|
| 动态分配 | 根据结果质量自适应，信息利用率高 | 实现稍复杂 | ✅ 选用 |
| 固定预算 | 简单 | 可能浪费预算或信息不足 | 不选用 |

---

## 8. 总结

### 核心创新点

1. **Qdrant-First**: 所有数据存储和检索都基于 Qdrant，充分展示向量数据库能力
2. **LLM-Driven Tool Selection**: 意图识别和工具选择合并，由 LLM 动态决策
3. **Dynamic Token Budgeting**: 基于相关性分数动态分配上下文预算
4. **Pre-computed Visual Semantics**: 视觉描述预生成，避免实时 VLM 调用

### 下一步工作

1. 实现 `agent/tool_selector.py` - LLM 工具选择模块
2. 实现 `agent/tools/` - 7 个工具的 Qdrant 查询实现
3. 实现 `agent/context_assembler.py` - 动态上下文组装
4. 更新 `scripts/ingest_v2.py` - 支持新的 collections
5. 集成测试 - 端到端流程验证

