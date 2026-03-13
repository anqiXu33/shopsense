#!/bin/bash
# launch.sh - Launch ShopSense v2

echo "🛍️  Starting ShopSense v2..."
echo "================================"

# Check Qdrant
echo "Checking Qdrant connection..."
if curl -s http://127.0.0.1:6333 > /dev/null; then
    echo "✓ Qdrant is running"
else
    echo "✗ Qdrant not found at http://127.0.0.1:6333"
    echo "Please start Qdrant first:"
    echo "  docker run -p 6333:6333 qdrant/qdrant"
    exit 1
fi

# Check collections
echo "Checking data collections..."
python3 -c "
from qdrant_client import QdrantClient
c = QdrantClient('http://127.0.0.1:6333')
cols = [col.name for col in c.get_collections().collections if 'v2' in col.name]
if len(cols) >= 4:
    print(f'✓ Found {len(cols)} collections')
else:
    print('⚠ Collections not found, running ingest...')
    import os
    os.system('python3 scripts/ingest_v2.py')
" 2>/dev/null

echo ""
echo "🚀 Launching Gradio UI..."
echo "================================"
python3 frontend/app_v2.py
