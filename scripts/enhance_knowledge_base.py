#!/usr/bin/env python3
"""
scripts/enhance_knowledge_base.py

增强知识库，添加更多常见材质和话题的知识
"""

import sys
sys.path.insert(0, '/Users/xzy/Desktop/shopsense')

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS

def get_client():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def add_enhanced_knowledge():
    """添加增强的知识库数据"""
    client = get_client()
    collection_name = QDRANT_COLLECTIONS["knowledge"]
    
    print("增强知识库...")
    
    enhanced_knowledge = [
        # 羽绒相关
        {
            "topic": "material",
            "material": "down",
            "category": "insulation",
            "content": "羽绒（Down）是鸟类羽毛的保暖层，具有极佳的保暖性和轻量性。蓬松度（Fill Power）越高，保暖性越好。650FP适合-5°C，800FP适合-15°C以下。",
            "properties": " lightweight, compressible, excellent warmth retention",
            "skin_notes": "羽绒本身不直接接触皮肤，外层通常为尼龙或聚酯纤维，敏感肌通常可以接受",
            "warmth_range": "650FP: -5°C to -10°C, 800FP: -15°C and below",
            "care_instructions": "建议干洗，避免频繁水洗，晾晒时拍打恢复蓬松"
        },
        {
            "topic": "warmth",
            "material": "down",
            "category": "insulation",
            "content": "羽绒服保暖性取决于蓬松度(Fill Power)和充绒量。650蓬松度适合日常冬季-5°C左右，800蓬松度可应对-15°C极寒。充绒量300g以上适合严寒地区。",
            "properties": "Fill Power 650-800+, fill weight 300g-500g",
            "skin_notes": "Inner lining prevents direct contact, generally safe",
            "warmth_range": "300g: -5°C, 400g: -10°C, 500g+: -15°C and below",
            "care_instructions": "Professional cleaning recommended, air dry thoroughly"
        },
        {
            "topic": "skin",
            "material": "down",
            "category": "insulation",
            "content": "羽绒服对敏感肌友好。羽绒被外壳面料包裹，不直接接触皮肤。外壳通常为聚酯纤维或尼龙，不易引起过敏。极少数人对羽绒蛋白过敏。",
            "properties": "Hypoallergenic when properly encased",
            "skin_notes": "Generally safe for sensitive skin. Outer shell prevents contact. Rare feather protein allergy possible.",
            "warmth_range": "N/A",
            "care_instructions": "Keep clean to prevent dust mite accumulation"
        },
        
        # 羊毛相关
        {
            "topic": "material",
            "material": "wool",
            "category": "fabric",
            "content": "羊毛是天然蛋白质纤维，具有优异的保暖性和吸湿排汗功能。美利奴羊毛纤维细腻，不易扎人。适合制作保暖内衣和冬季外套。",
            "properties": "Warm, moisture-wicking, breathable, odor-resistant",
            "skin_notes": "Merino wool is gentle and suitable for most skin types. Regular wool may itch sensitive skin.",
            "warmth_range": "Suitable for 0°C to 15°C depending on weight",
            "care_instructions": "Hand wash or gentle cycle, lay flat to dry"
        },
        {
            "topic": "skin",
            "material": "wool",
            "category": "fabric",
            "content": "美利奴羊毛适合敏感肌，纤维细度低于24微米不易引起刺痒。普通羊毛较粗，可能引起皮肤不适。建议敏感肌选择标注'防过敏'或'美利奴'的羊毛产品。",
            "properties": "Fine merino wool suitable for sensitive skin",
            "skin_notes": "Merino wool (<24 microns) is generally safe. Coarse wool may cause itching. Test before prolonged wear.",
            "warmth_range": "N/A",
            "care_instructions": "Use wool-specific detergent"
        },
        
        # 羊绒相关
        {
            "topic": "material",
            "material": "cashmere",
            "category": "fabric",
            "content": "羊绒是山羊绒的细软绒毛，比羊毛更轻、更暖、更柔软。纤维直径15-19微米，不扎皮肤，是高端保暖材料。价格较高，需要精心护理。",
            "properties": "Ultra-soft, lightweight, 3x warmer than wool, breathable",
            "skin_notes": "Extremely gentle, suitable for sensitive skin and babies. No itch or irritation.",
            "warmth_range": "0°C to 10°C for sweaters, -5°C for coats",
            "care_instructions": "Dry clean recommended, hand wash with care, never wring"
        },
        
        # 棉相关
        {
            "topic": "material",
            "material": "cotton",
            "category": "fabric",
            "content": "棉花是天然植物纤维，柔软透气，吸湿性好。适合春夏穿着和贴身衣物。但保暖性不如羊毛羽绒，湿水后保暖性下降明显。",
            "properties": "Soft, breathable, hypoallergenic, affordable",
            "skin_notes": "Best for sensitive skin and allergies. Very gentle and non-irritating.",
            "warmth_range": "15°C and above, not suitable for cold weather",
            "care_instructions": "Machine washable, easy care"
        },
        
        # 聚酯纤维相关
        {
            "topic": "material",
            "material": "polyester",
            "category": "fabric",
            "content": "聚酯纤维是合成纤维，耐用、快干、不易皱。抓绒（Fleece）形式的聚酯纤维保暖性很好。但透气性不如天然纤维，可能产生静电。",
            "properties": "Durable, quick-dry, wrinkle-resistant, affordable",
            "skin_notes": "May cause static and slight irritation for very sensitive skin. Choose soft microfiber variants.",
            "warmth_range": "Fleece: 5°C to 15°C",
            "care_instructions": "Machine washable, quick drying"
        },
        {
            "topic": "skin",
            "material": "polyester",
            "category": "fabric",
            "content": "聚酯纤维对大多数人安全，但透气性较差可能导致闷热。极少数敏感肌可能对化学纤维不适。建议选择柔软处理过的面料。",
            "properties": "Generally safe but less breathable",
            "skin_notes": "Generally safe. May trap heat and sweat. Choose breathable weaves for sensitive skin.",
            "warmth_range": "N/A",
            "care_instructions": "Wash regularly to prevent odor buildup"
        },
        
        # 尺码相关
        {
            "topic": "sizing",
            "material": "general",
            "category": "guide",
            "content": "亚洲尺码通常比欧美尺码小1-2个码。羽绒服等外套建议选大一码以便内搭。网购时查看详细的胸围、肩宽、袖长数据更准确。",
            "properties": "Size conversion guide",
            "skin_notes": "N/A",
            "warmth_range": "N/A",
            "care_instructions": "Measure before purchase"
        },
        
        # 保暖性通用
        {
            "topic": "warmth",
            "material": "general",
            "category": "guide",
            "content": "冬季保暖 layering 三层原则：内层排汗（美利奴羊毛/合成纤维）、中层保暖（羽绒/抓绒）、外层防风（硬壳外套）。根据活动强度和环境温度调整。",
            "properties": "Layering system guide",
            "skin_notes": "Choose base layers suitable for your skin type",
            "warmth_range": "Adjust based on activity and environment",
            "care_instructions": "N/A"
        }
    ]
    
    # 获取当前最大ID
    existing = client.scroll(collection_name=collection_name, limit=1)[0]
    start_id = 200  # 从200开始，避免冲突
    
    points = []
    for i, item in enumerate(enhanced_knowledge):
        # 构建搜索文本
        text = f"{item['material']} {item['topic']}: {item['content']} "
        text += f"Properties: {item['properties']}. "
        text += f"Skin notes: {item['skin_notes']}. "
        text += f"Warmth: {item['warmth_range']}."
        
        vector = embed(text)
        points.append(PointStruct(
            id=start_id + i,
            vector=vector,
            payload=item
        ))
    
    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 添加了 {len(points)} 条增强知识")
    
    return len(points)

def test_knowledge_retrieval():
    """测试知识检索"""
    print("\n测试知识检索...")
    
    from agent.tools import get_tool_instance
    import asyncio
    
    test_queries = [
        ("羽绒服保暖吗", "down", "warmth"),
        ("敏感肌能穿羊毛吗", "wool", "skin"),
        ("羊绒怎么样", "cashmere", "material"),
        ("聚酯纤维对皮肤好吗", "polyester", "skin"),
    ]
    
    tool = get_tool_instance("knowledge_retrieval")
    
    for query, material, topic in test_queries:
        print(f"\n查询: {query}")
        result = asyncio.run(tool.execute(
            query=query,
            material=material,
            topic=topic,
            top_k=2
        ))
        
        if result.success and result.data.get("knowledge_items"):
            items = result.data["knowledge_items"]
            print(f"  ✅ 找到 {len(items)} 条知识")
            for item in items:
                print(f"    - {item['content'][:60]}...")
        else:
            print(f"  ❌ 未找到知识")

def main():
    print("="*60)
    print("增强知识库")
    print("="*60)
    
    try:
        count = add_enhanced_knowledge()
        print(f"\n✅ 知识库增强完成！添加了 {count} 条新知识")
        
        # 测试检索
        test_knowledge_retrieval()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
