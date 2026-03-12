"""
scripts/add_conflict_test_data.py

添加存在冲突的测试数据到 Qdrant
用于测试冲突检测功能
"""

import sys
sys.path.insert(0, '/Users/xzy/Desktop/shopsense')

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from core.embeddings import embed
from config.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTIONS

def get_client():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def add_conflict_reviews():
    """添加与知识库冲突的评价数据"""
    client = get_client()
    collection_name = QDRANT_COLLECTIONS["reviews"]
    
    print("添加冲突测试评价...")
    
    # 场景1: 知识库说羊毛安全，但用户评价说过敏
    conflict_reviews_1 = [
        {
            "asin": "P004",  # Merino Wool Base Layer
            "text": "Terrible experience! I have sensitive skin and this wool caused severe itching and rash all over my body. Had to return it immediately.",
            "rating": 1,
            "sentiment": "negative",
            "reviewer_height": 170,
            "reviewer_weight": 65,
            "verified_purchase": True
        },
        {
            "asin": "P004",
            "text": "Broke out in hives after wearing this for 2 hours. If you have sensitive skin, AVOID this product! The wool is very irritating.",
            "rating": 2,
            "sentiment": "negative",
            "reviewer_height": 165,
            "reviewer_weight": 55,
            "verified_purchase": True
        },
        {
            "asin": "P004",
            "text": "Supposed to be safe for sensitive skin but caused redness and itching. Very disappointed.",
            "rating": 2,
            "sentiment": "negative",
            "reviewer_height": 168,
            "reviewer_weight": 60,
            "verified_purchase": True
        }
    ]
    
    # 场景2: 知识库说650FP保暖，但用户评价说不保暖
    conflict_reviews_2 = [
        {
            "asin": "P001",  # Alpine Duck Down Jacket
            "text": "Not warm at all! Wore this in -5°C weather and was freezing. The fill power is totally insufficient for cold weather.",
            "rating": 2,
            "sentiment": "negative",
            "reviewer_height": 175,
            "reviewer_weight": 70,
            "verified_purchase": True
        },
        {
            "asin": "P001",
            "text": "Very disappointed with the warmth. At -10°C I was shivering. The jacket looks thick but provides poor insulation.",
            "rating": 1,
            "sentiment": "negative",
            "reviewer_height": 172,
            "reviewer_weight": 68,
            "verified_purchase": True
        },
        {
            "asin": "P001",
            "text": "Claimed to be warm for winter but I was cold even at 0°C. Don't buy if you need real warmth.",
            "rating": 2,
            "sentiment": "negative",
            "reviewer_height": 170,
            "reviewer_weight": 65,
            "verified_purchase": True
        }
    ]
    
    # 场景3: 高品质声明 vs 质量差的评价
    conflict_reviews_3 = [
        {
            "asin": "P002",  # Waterproof Trench Coat
            "text": "Poor quality! The zipper broke after 2 weeks of use. Very disappointed with the craftsmanship.",
            "rating": 1,
            "sentiment": "negative",
            "reviewer_height": 168,
            "reviewer_weight": 62,
            "verified_purchase": True
        },
        {
            "asin": "P002",
            "text": "Cheap materials. The seams are coming apart after one month. Not worth the price.",
            "rating": 2,
            "sentiment": "negative",
            "reviewer_height": 165,
            "reviewer_weight": 58,
            "verified_purchase": True
        }
    ]
    
    all_reviews = conflict_reviews_1 + conflict_reviews_2 + conflict_reviews_3
    
    # 获取当前最大ID
    existing = client.scroll(collection_name=collection_name, limit=1)[0]
    start_id = 100  # 从100开始，避免冲突
    
    points = []
    for i, review in enumerate(all_reviews):
        vector = embed(review["text"])
        points.append(PointStruct(
            id=start_id + i,
            vector=vector,
            payload=review
        ))
    
    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 添加了 {len(points)} 条冲突测试评价")
    
    return len(points)

def add_conflict_knowledge():
    """添加与评价冲突的知识库数据"""
    client = get_client()
    collection_name = QDRANT_COLLECTIONS["knowledge"]
    
    print("添加冲突测试知识...")
    
    # 明确声明安全但实际有问题的知识
    conflict_knowledge = [
        {
            "topic": "skin",
            "material": "merino_wool",
            "category": "fabric",
            "content": "Merino wool is hypoallergenic and safe for all skin types including sensitive skin. The fine fibers are gentle and non-irritating.",
            "properties": "Hypoallergenic, gentle, safe for sensitive skin",
            "skin_notes": "Hypoallergenic. Safe for sensitive skin and eczema. No known skin reactions.",
            "warmth_range": "Mild to cold",
            "care_instructions": "Hand wash or gentle machine wash"
        },
        {
            "topic": "warmth",
            "material": "duck_down",
            "category": "insulation",
            "content": "650FP duck down with 450g fill provides excellent warmth suitable for -10°C to -15°C environments. High warmth-to-weight ratio.",
            "properties": "Excellent insulation, high warmth-to-weight ratio",
            "skin_notes": "Outer shell prevents direct contact, safe for most users",
            "warmth_range": "Suitable for -10°C to -15°C, cold winter conditions",
            "care_instructions": "Professional cleaning recommended"
        },
        {
            "topic": "quality",
            "material": "polyester_blend",
            "category": "fabric",
            "content": "Premium polyester blend fabric with high-quality construction. Durable zippers and reinforced seams ensure long-lasting performance.",
            "properties": "High quality, durable, premium construction",
            "skin_notes": "May cause slight irritation for very sensitive skin",
            "warmth_range": "Depends on thickness",
            "care_instructions": "Machine washable"
        }
    ]
    
    # 获取当前最大ID
    existing = client.scroll(collection_name=collection_name, limit=1)[0]
    start_id = 100
    
    points = []
    for i, item in enumerate(conflict_knowledge):
        text = f"{item['material']}: {item['content']} {item['properties']} Skin notes: {item['skin_notes']} Warmth: {item['warmth_range']}"
        vector = embed(text)
        points.append(PointStruct(
            id=start_id + i,
            vector=vector,
            payload=item
        ))
    
    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ 添加了 {len(points)} 条冲突测试知识")
    
    return len(points)

def test_conflict_detection():
    """测试冲突检测"""
    print("\n测试冲突检测...")
    
    from agent.tool_selector import select_tools
    from agent.executor import execute_tools
    from agent.conflict_detector import detect_conflicts, format_conflicts
    
    # 测试场景1: 敏感肌冲突
    print("\n场景1: 敏感肌安全 vs 用户过敏反馈")
    reasoning, tool_calls = select_tools(
        user_query="Merino wool safe for sensitive skin?",
        current_asin="P004"
    )
    
    print(f"Selected tools: {[tc['name'] for tc in tool_calls]}")
    
    results = execute_tools(tool_calls)
    conflicts = detect_conflicts(results)
    
    if conflicts:
        print(f"✅ 检测到 {len(conflicts)} 个冲突:")
        print(format_conflicts(conflicts))
    else:
        print("❌ 未检测到冲突")
    
    # 测试场景2: 保暖性冲突
    print("\n场景2: 保暖性声明 vs 用户反馈不保暖")
    reasoning, tool_calls = select_tools(
        user_query="这件羽绒服保暖吗？",
        current_asin="P001"
    )
    
    results = execute_tools(tool_calls)
    conflicts = detect_conflicts(results)
    
    if conflicts:
        print(f"✅ 检测到 {len(conflicts)} 个冲突:")
        for c in conflicts:
            print(f"   - {c.conflict_type}: {c.description[:50]}...")
    else:
        print("❌ 未检测到冲突")

def main():
    print("="*60)
    print("添加冲突测试数据")
    print("="*60)
    
    try:
        n_reviews = add_conflict_reviews()
        n_knowledge = add_conflict_knowledge()
        
        print(f"\n✅ 数据添加完成!")
        print(f"   冲突评价: {n_reviews} 条")
        print(f"   冲突知识: {n_knowledge} 条")
        
        # 测试冲突检测
        test_conflict_detection()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
