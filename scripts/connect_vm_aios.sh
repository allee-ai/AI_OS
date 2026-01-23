#!/bin/bash

# AI OS VM Connection Script
# Establishes SSH tunnel and opens browser to access VM-hosted AI OS

VM_HOST="root@YOUR_VM_IP"  # Replace with your actual VM IP
LOCAL_PORT="8000"
VM_PORT="8000"

echo "🚀 Connecting to AI OS VM..."

# Kill any existing SSH tunnels to avoid conflicts
pkill -f "ssh.*$VM_HOST.*$LOCAL_PORT:localhost:$VM_PORT" 2>/dev/null

# Check if VM is reachable
if ! ssh -o ConnectTimeout=5 "$VM_HOST" "exit" 2>/dev/null; then
    echo "❌ Cannot connect to VM at $VM_HOST"
    echo "   Check your internet connection and VM status"
    exit 1
fi

# Check if AI OS service is running on VM
if ! ssh "$VM_HOST" "systemctl is-active --quiet aios"; then
    echo "⚠️  AI OS service not running on VM. Starting..."
    ssh "$VM_HOST" "systemctl start aios"
    sleep 3
fi

echo "🔗 Creating SSH tunnel..."
# Create SSH tunnel in background
ssh -L "$LOCAL_PORT:localhost:$VM_PORT" "$VM_HOST" -N &
SSH_PID=$!

# Wait for tunnel to establish
sleep 2

# Check if local port is now available
if ! curl -s "http://localhost:$LOCAL_PORT/api/health" >/dev/null 2>&1; then
    echo "⏳ Waiting for AI OS to respond..."
    sleep 3
fi

echo "🌐 Opening AI OS in browser..."
# Open browser (macOS)
open "http://localhost:$LOCAL_PORT"

echo "✅ AI OS VM connection established!"
echo "   🔗 SSH Tunnel PID: $SSH_PID"
echo "   🌍 Browser: http://localhost:$LOCAL_PORT"
echo "   📡 VM: $VM_HOST"
echo ""
echo "To disconnect: kill $SSH_PID or close terminal"

# Keep script running to maintain tunnel
wait $SSH_PID