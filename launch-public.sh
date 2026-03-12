#!/bin/bash
# launch-public.sh - Launch ShopSense with Cloudflare public tunnel

echo "================================"
echo "🛍️  ShopSense 公网启动脚本"
echo "================================"
echo ""

# 1. 检查 Gradio
if ! curl -s http://127.0.0.1:7860 > /dev/null; then
    echo "🚀 启动 Gradio..."
    python3 frontend/app_v2.py > /tmp/gradio.log 2>&1 &
    sleep 5
fi

# 2. 检查本地服务
if curl -s http://127.0.0.1:7860 > /dev/null; then
    echo "✅ Gradio 运行在 http://127.0.0.1:7860"
else
    echo "❌ Gradio 启动失败"
    exit 1
fi

# 3. 停止旧的 tunnel
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

# 4. 启动新的 quick tunnel
echo ""
echo "🌐 启动 Cloudflare Tunnel..."
cloudflared tunnel --url http://localhost:7860 2>&1 &

# 5. 等待并提取域名
echo ""
echo "⏳ 等待生成公网域名..."
sleep 8

# 从日志中提取域名
URL=$(grep -o 'https://[a-z0-9-]*.trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | tail -1)

if [ -n "$URL" ]; then
    echo ""
    echo "================================"
    echo "✅ ShopSense 已成功部署到公网！"
    echo "================================"
    echo ""
    echo "🌍 公网访问地址："
    echo "   $URL"
    echo ""
    echo "📱 其他访问方式："
    echo "   本地:     http://127.0.0.1:7860"
    echo "   局域网:   http://192.168.2.118:7860"
    echo ""
    echo "🔒 自动启用 HTTPS"
    echo ""
    echo "⚠️  注意："
    echo "   - 每次启动都会生成新的随机域名"
    echo "   - 关闭终端后服务会停止"
    echo "   - 如需固定域名，请配置 named tunnel"
    echo "================================"
    echo ""
    echo "按 Ctrl+C 停止服务"
    wait
else
    echo ""
    echo "⚠️  获取域名失败，请查看日志："
    echo "   tail -f /tmp/cloudflared.log"
    echo ""
    echo "手动访问 http://127.0.0.1:7860 测试本地服务"
fi
