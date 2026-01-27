# AI OS — A Control Layer for Your LLM

**Turn any local model into a personal AI that remembers, learns, and stays consistent. Private. Free. Yours.**

![CI](https://github.com/allee-ai/AI_OS/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## What is AI OS?

LLMs are powerful but unreliable. They hallucinate, forget, lose track of who they are, and treat every conversation like it's the first.

AI OS fixes that. It's a management layer that wraps your local LLM and handles everything the model is bad at:

- **Memory** — Persistent across sessions, organized by relevance
- **Identity** — Consistent personality that can't be prompt-injected away  
- **Learning** — Gets smarter from experience, not retraining
- **Control** — LLM only handles language; the OS handles logic

The LLM is the voice. The OS is the brain.

---

## Getting Started (5 minutes)

### What You'll Need

- A Mac, Windows, or Linux computer
- About 8GB of free disk space
- Internet connection (just for the initial setup)

### Step 1: Download AI OS

You can download AI OS in two ways:

1. **From the Website:**
   - Visit [https://allee-ai.com/download](https://allee-ai.com/download) and download the latest version for your operating system.
   - Extract the downloaded file and open the folder.

2. **From GitHub:**
   - Open your terminal (on Mac: search "Terminal" in Spotlight) and run:

     ```bash
     git clone https://github.com/allee-ai/AI_OS.git
     cd AI_OS
     ```

### Step 2: Run AI OS

Simply double-click `run.command` (on Mac/Linux) or `run.bat` (on Windows) in the downloaded folder. This script handles everything:

- ✅ Installs the LLM runtime (Ollama)
- ✅ Starts the OS backend and chat interface
- ✅ Opens your browser automatically

> **First time?** The first launch downloads the AI model (~4GB). This only happens once.

### Step 3: Start Chatting!

Your browser will open to `http://localhost:5173` — start talking to your AI.

---

## How Memory Works

```
You: "I'm working on a Python project called TaskMaster"
     ↓
OS stores this in your profile (not in the LLM)
     ↓
Later... (even days later, even after restarts)
     ↓
You: "How's my project going?"
AI: "TaskMaster? Or, one of your other projects {list}"
```

**The LLM didn't remember that. The OS did.** Your facts live in a database, organized by relevance, retrieved when needed. The LLM just turns that context into natural language.

---

## Make It Yours

### Name Your AI

Edit `agent/Agent.json`:

```json
{
  "name": "Friday",
  "personality": "dry wit, competent, anticipates needs",
  "greeting": "What do you need?"
}
```

The name is just a key. Call it Jarvis, Friday, whatever. The OS doesn't care.

### Tell It About Yourself

Edit `agent/identity_thread/userID/user.json`:

```json
{
  "name": "Alex",
  "occupation": "software developer",
  "interests": ["gaming", "cooking", "hiking"],
  "preferences": {
    "communication_style": "direct, no fluff"
  }
}
```

It's still prompting — just organized. **Hybrid human/program prompting.** You define who you are, the OS decides what's relevant right now, and together they build context the LLM can actually use. Easier for you to manage. Easier for the LLM to understand.

---

## Frequently Asked Questions

### Is my data really private?

**Yes.** Everything runs on your computer. Your conversations, memories, and profile are stored locally in SQLite, not on any server.

### Do I need internet after setup?

**No.** Once installed, AI OS works completely offline.

### How much does it cost?

**$0.** Open source, MIT licensed, free forever.

### What computer specs do I need?

| | Minimum | Recommended |
|---|---------|-------------|
| RAM | 8GB | 16GB |
| Storage | 8GB free | 15GB free |
| OS | macOS 10.15+, Windows 10+, Ubuntu 20.04+ | Same |

### Can I use a different AI model?

Yes! Edit `.env` and change `OLLAMA_MODEL` to any model Ollama supports. Try `llama3.1` for more capabilities or `phi3` for faster responses.

### Something broke!

1. Close everything and run `./start.sh` again
2. Make sure no other app is using port 5173 or 8000
3. Check [Troubleshooting](docs/implementation/troubleshooting.md)
4. Open an [issue on GitHub](https://github.com/allee-ai/AI_OS/issues)

---

## What Can You Do With It?

| Use Case | Without OS | With AI OS |
|----------|-----------|------------|
| **Context** | "Who am I talking to?" | Knows your name, job, projects, preferences |
| **Continuity** | Every conversation starts fresh | Picks up where you left off, even weeks later |
| **Consistency** | Personality drifts with prompting | Identity is structural, can't be manipulated |
| **Learning** | Same quality forever | Gets better as it learns your patterns |

---

## The Architecture

This isn't a chatbot wrapper. It's a cognitive operating system.

### LLM vs OS Responsibilities

| Task | Who Handles It |
|------|----------------|
| Generating natural language | LLM |
| Remembering facts about you | OS (SQLite) |
| Maintaining consistent identity | OS (identity thread) |
| Connecting related concepts | OS (Hebbian linking) |
| Deciding what context is relevant | OS (HEA attention) |
| Learning from experience | OS (pattern consolidation) |

The LLM is stateless and dumb. The OS makes it smart.

### The Roadmap

See **[docs/ROADMAP.md](docs/ROADMAP.md)** for the full vision:
- ✅ **Now:** Subconscious, memory threads, HEA context levels
- 🔄 **Next:** Memory consolidation, philosophy constraints
- 🚀 **Future:** Reflex automation, dream states, multi-model routing, enterprise integration

---

## Looking for Collaborators

Built solo since April 2025. The architecture works. Now it needs to scale.

**Looking for:**
- **Python devs** — async, SQLite, state management
- **React devs** — dashboard UI, visualizations
- **AI researchers** — cognitive architecture, memory systems
- **Anyone frustrated with raw LLMs** — use it, break it, tell me what's missing

**Interested?** Open an issue, start a discussion, or just start using it.

---

## Learn More

| Guide | Description |
|-------|-------------|
| [**Roadmap**](docs/ROADMAP.md) | Where this is going and how to help |
| [**Developer Guide**](DEVELOPERS.md) | Build features, understand the code |
| [**All Documentation**](docs/README.md) | Full documentation index |
| [**Architecture**](agent/ARCHITECTURE.md) | Technical deep-dive (threads, HEA, Hebbian linking) |
| [**Contributing**](CONTRIBUTING.md) | Help build it |

---

## Get Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/allee-ai/AI_OS/issues)
- **Discussions:** Share how you're using Nola

---

*Your LLM is powerful. It just needs a brain.*
