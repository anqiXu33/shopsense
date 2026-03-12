#!/bin/bash
# Launch ShopSense with LAN access

echo "🛍️  ShopSense v2 - LAN Mode"
echo "================================"

# Get IP addresses
echo ""
echo "📱 Network Interfaces:"
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "   " $2}'

# Get hostname
HOSTNAME=$(hostname)
echo ""
echo "👤 Hostname: $HOSTNAME"
echo ""
echo "🚀 Starting server on 0.0.0.0:7860..."
echo "================================"

python3 frontend/app_v2.py
