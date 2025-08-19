#!/bin/bash

echo "🚀 Starting Password-Protected Chatbot Report Server..."
echo ""

# Check if Python is available
if command -v python3 &> /dev/null; then
    python3 password_server.py
elif command -v python &> /dev/null; then
    python password_server.py
else
    echo "❌ Error: Python not found!"
    echo "   Please install Python 3.6+ to run this server"
    exit 1
fi
