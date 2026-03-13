# Draft: ShopSense 架构升级 - Qdrant 深度结合版

## 核心原则
- 所有数据存 Qdrant
- 充分利用 Qdrant 的向量搜索 + Payload 过滤 + 混合检索
- 减少外部依赖，突出 Qdrant 的能力

## Qdrant Collections 设计（修订版）

### Collection 1: `products`
- 向量：商品描述 + 标题
- Payload: asin, name, brand, category, price, attributes, image_url
- 用途：商品语义搜索、属性过滤

### Collection 2: `reviews`  
- 向量：评价文本
- Payload: asin, text, rating, sentiment, reviewer_height, reviewer_weight, helpful_votes, verified_purchase
- 用途：评价语义检索、多维度过滤

### Collection 3: `knowledge`
- 向量：专业知识文本
- Payload: topic, material, category, source
- 用途：材料知识、尺码标准、保养建议

### Collection 4: `visual_semantic`
- 向量：图片视觉描述（由 VLM 预生成）
- Payload: asin, image_type, description, attributes(color, style, texture)
- 用途：视觉语义搜索

### Collection 5: `qa_pairs` (新增)
- 向量：历史问答对
- Payload: question, answer, asin, helpful_count
- 用途：相似问题检索、FAQ

## 工具与 Qdrant 的映射

| 工具 | Qdrant 操作 |
|------|-------------|
| semantic_search | query_points with filters |
| review_mining | query_points + payload filter + grouping |
| knowledge_query | query_points on knowledge collection |
| visual_search | query_points on visual_semantic |
| similar_questions | query_points on qa_pairs |
| facet_analysis | facet API (Qdrant 1.8+) |

## Qdrant 特性利用

1. **Hybrid Search**: 稠密向量(embedding) + 稀疏向量(BM25)
2. **Payload Indexes**: 加快 asin, sentiment, rating 过滤
3. **Discovery API**: 找相似商品/评价
4. **Recommend API**: 基于正负例推荐
5. **Grouping**: 按 asin 聚合评价
6. **Prefech**: 多查询批量执行
