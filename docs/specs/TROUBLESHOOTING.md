# Troubleshooting

Common problems and how to fix them.

---

## Nola Won't Start

### "Command not found: ./start.sh"

**Fix:** Make the script executable:
```bash
chmod +x start.sh
./start.sh
```

### "Ollama not found"

**Fix:** Install Ollama:
- **Mac:** `brew install ollama`
- **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`
- **Windows:** Download from [ollama.com](https://ollama.com)

Then try again:
```bash
./start.sh
```

### "Port already in use"

**Fix:** Something else is using port 5173 or 8000.

Find and kill it:
```bash
# Find what's using port 8000
lsof -i :8000

# Kill it (replace PID with the number you see)
kill -9 PID
```

Or use different ports:
```bash
# Backend
uvicorn main:app --port 8001

# Frontend (edit vite.config.ts or use)
npm run dev -- --port 5174
```

---

## Chat Not Working

### "Connection refused" or blank screen

1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```
   Should return `{"status": "healthy"}`

2. **Check Ollama is running:**
   ```bash
   ollama list
   ```
   Should show your model (e.g., `qwen2.5:7b`)

3. **Restart everything:**
   ```bash
   # Kill existing processes
   pkill -f uvicorn
   pkill -f "npm run dev"
   
   # Start fresh
   ./start.sh
   ```

### Nola responds but doesn't remember things

The memory system might not be connected. Check:
```bash
# From project root
python3 -c "from Nola.subconscious import wake, get_status; wake(); print(get_status())"
```

All threads should show "ok" status.

---

## Performance Issues

### Slow responses

1. **Try a smaller model:**
   Edit `.env`:
   ```
   OLLAMA_MODEL=phi3
   ```

2. **Check available RAM:**
   ```bash
   # Mac/Linux
   free -h
   
   # Or
   top
   ```
   Need at least 8GB free for good performance.

3. **Close other applications** using GPU/RAM.

### High CPU/Memory usage

Ollama can be resource-intensive. Options:
- Use a smaller model (`phi3` instead of `llama3.1`)
- Close Ollama when not using Nola: `ollama stop`

---

## Data Issues

### "Where are my conversations?"

Stored in: `Nola/Stimuli/conversations/`

Each file is named `react_YYYYMMDD_HHMMSS.json`.

### "Nola forgot everything"

Check if identity files exist:
```bash
ls Nola/identity_thread/userID/
ls Nola/Nola.json
```

If missing, they'll be recreated on next start with defaults.

### Reset Nola completely

⚠️ **This deletes all memory and conversations:**

```bash
rm -rf Nola/Stimuli/conversations/*
rm -rf data/db/state.db
rm Nola/Nola.json
```

Then restart: `./start.sh`

---

## Still Stuck?

1. **Check the logs:**
   ```bash
   cat Nola/LOG.txt
   ```

2. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

3. **Open an issue:** [GitHub Issues](https://github.com/allee-ai/AI_OS/issues)

Include:
- What you tried
- Error messages
- Your OS and Python version (`python3 --version`)
