# VM Deployment Guide

Deploy Agent AI OS to a cloud VM for 24/7 always-on operation.

---

## Prerequisites

- **DigitalOcean account** (or similar VPS provider)
- **SSH key** configured locally (~/.ssh/id_rsa or similar)
- **Local AI_OS repo** with your changes pushed to GitHub

---

## Step 1: Create VM

### DigitalOcean Droplet Specs (Recommended)
- **Image**: Ubuntu 22.04 LTS
- **Size**: 8GB RAM, 4 vCPU, 160GB SSD (~$40/month)
- **Region**: Choose closest to you
- **SSH Key**: Add your existing SSH key

### After Creation
Note your VM's IP address (e.g., `YOUR_VM_IP`)

---

## Step 2: Initial Setup

SSH into your new VM:
```bash
ssh root@YOUR_VM_IP
```

Clone the repository:
```bash
cd ~
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
```

Run the VM installer:
```bash
chmod +x install-vm.sh
./install-vm.sh
```

This installs:
- Python 3.12 with virtual environment
- Node.js 18+
- Ollama (local LLM runtime)
- All Python dependencies
- All Node dependencies

---

## Step 3: Pull Ollama Model

Choose a lightweight model for testing:
```bash
ollama pull qwen2:1.5b
```

Optional heavier model:
```bash
ollama pull llama2:7b
```

---

## Step 4: Build Frontend

```bash
cd ~/AI_OS/agent/react-chat-app/frontend
npm install
npm run build
```

---

## Step 5: Configure Static File Serving

The backend needs to serve the frontend. Add to `main.py`:

```python
from fastapi.staticfiles import StaticFiles

# At the end of your router includes:
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

---

## Step 6: Create Systemd Service

Create the service file:
```bash
cat > /etc/systemd/system/nola.service << 'EOF'
[Unit]
Description=Nola AI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/AI_OS/agent/react-chat-app/backend
Environment=AIOS_MODE=personal
Environment=DEV_MODE=true
Environment=PYTHONPATH=/root/AI_OS
ExecStart=/root/AI_OS/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable nola
systemctl start nola
```

Check status:
```bash
systemctl status nola
```

---

## Step 7: Migrate Your Data

From your **local machine**, copy your personal database:
```bash
scp ./data/db/state.db root@YOUR_VM_IP:/root/AI_OS/data/db/
scp ./agent/identity.json root@YOUR_VM_IP:/root/AI_OS/agent/
scp -r ./agent/workspace/ root@YOUR_VM_IP:/root/AI_OS/agent/
```

Restart service to pick up new data:
```bash
ssh root@YOUR_VM_IP "systemctl restart nola"
```

---

## Step 8: Create Local Connection Script

On your **local machine**, create `Connect to Agent VM.command`:
```bash
#!/bin/bash

echo "🚀 Connecting to Agent VM..."

pkill -f "ssh.*YOUR_VM_IP.*8000" 2>/dev/null
sleep 1

echo "📦 Deploying latest changes..."
ssh root@YOUR_VM_IP "cd AI_OS && git pull && systemctl restart nola"

echo "🔗 Creating SSH tunnel..."
ssh -L 8000:localhost:8000 root@YOUR_VM_IP -N &
SSH_PID=$!

sleep 5

if curl -s --max-time 10 "http://localhost:8000/" >/dev/null 2>&1; then
    echo "✅ Connection established!"
    open "http://localhost:8000"
    wait $SSH_PID
else
    echo "❌ Connection failed!"
    kill $SSH_PID 2>/dev/null
    exit 1
fi
```

Make executable:
```bash
chmod +x "Connect to Agent VM.command"
```

---

## Daily Workflow

1. **Develop locally** with hot reload
2. **Push changes**: `git push`
3. **Deploy + Access**: Double-click `Connect to Agent VM.command`

The connection script automatically:
- Pulls latest code from GitHub
- Restarts the Agent service
- Creates SSH tunnel
- Opens browser to your VM Nola

---

## Useful Commands

### Check Service Status
```bash
ssh root@YOUR_VM_IP "systemctl status nola"
```

### View Logs
```bash
ssh root@YOUR_VM_IP "journalctl -u nola -n 50 --no-pager"
```

### Restart Service
```bash
ssh root@YOUR_VM_IP "systemctl restart nola"
```

### Switch Modes
Edit `/etc/systemd/system/nola.service` and change:
- `AIOS_MODE=demo` or `AIOS_MODE=personal`
- `DEV_MODE=true` or `DEV_MODE=false`

Then:
```bash
ssh root@YOUR_VM_IP "systemctl daemon-reload && systemctl restart nola"
```

---

## Cost Breakdown

| Component | Cost |
|-----------|------|
| DigitalOcean Droplet (8GB) | ~$40/month |
| Domain (optional) | ~$12/year |
| **Total** | **~$40/month** |

---

## Security Notes

- VM uses your SSH key for authentication
- No password login enabled
- All traffic tunneled through SSH
- Consider adding UFW firewall rules for production
