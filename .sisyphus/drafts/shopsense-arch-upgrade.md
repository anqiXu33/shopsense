# Draft: ShopSense 架构升级 - 工具设计

## 架构确认
- 单步 Function Calling (Intent + Tool Selection 合并)
- OpenAI-compatible Function Calling 格式
- 并行工具执行
- 动态上下文组装

## 工具清单（讨论中）

### 候选工具
1. **product_info** - 商品基础信息
2. **product_details** - 商品详情分析
3. **visual_analysis** - 图片视觉分析
4. **review_search** - 评价检索
5. **review_summary** - 评价摘要
6. **web_search** - 外部搜索
7. **knowledge_lookup** - 专业知识查询
8. **size_recommend** - 尺码推荐
9. **comparison** - 竞品对比

## 待确定
- 具体每个工具的参数设计
- 工具调用策略（并行 vs 依赖）
- 工具结果如何影响 token 权重
