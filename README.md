# Nola — Your Personal AI That Actually Remembers You

**A private AI assistant that runs on your computer. No cloud. No subscriptions. Your data stays yours.**

![CI](https://github.com/allee-ai/AI_OS/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## What is Nola?

Nola is a personal AI that:
- **Remembers your conversations** — She learns what you like, your projects, your preferences
- **Runs 100% on your computer** — Nothing goes to the cloud
- **Gets smarter over time** — The more you chat, the better she understands you
- **Is completely free** — Open source, no subscriptions

Think of it like having a personal assistant who actually pays attention and remembers what you've talked about.

---

## Getting Started (5 minutes)

### What You'll Need

- A Mac, Windows, or Linux computer
- About 8GB of free disk space
- Internet connection (just for the initial setup)

### Step 1: Download Nola

Open your terminal (on Mac: search "Terminal" in Spotlight) and run:

```bash
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
```

> **Don't have git?** Download the ZIP from [GitHub](https://github.com/allee-ai/AI_OS) → green "Code" button → "Download ZIP", then unzip and open that folder in terminal.

### Step 2: Configure Environment (Optional)

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

> **Note:** The default settings work out of the box. Only edit `.env` if you want to add API keys for extended features (Kernel browser automation, Linear integration, etc.)

### Step 3: Start Nola

**Mac/Linux:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

That's it! The script handles everything:
- ✅ Installs the AI brain (Ollama)
- ✅ Sets up the chat interface
- ✅ Opens your browser automatically

> **First time?** The first launch downloads the AI model (~4GB). This only happens once.

### Step 3: Start Chatting!

Your browser will open to `http://localhost:5173` — just start talking to Nola!

---

## How Nola Remembers Things

```
You: "I'm working on a Python project called TaskMaster"
     ↓
Nola saves this fact about you
     ↓
Later...
     ↓
You: "How's my project going?"
Nola: "How's TaskMaster coming along? Need any Python help?"
```

**The more you chat, the more she learns.** Mention your job, hobbies, preferences — she'll remember and use that in future conversations.

---

## Customizing Nola

### Change Her Name or Personality

Edit `Nola/Nola.json`:

```json
{
  "name": "Aria",
  "personality": "friendly and enthusiastic",
  "greeting": "Hey there! What's on your mind?"
}
```

### Tell Her About Yourself

Edit `Nola/identity_thread/userID/user.json`:

```json
{
  "name": "Alex",
  "occupation": "software developer",
  "interests": ["gaming", "cooking", "hiking"],
  "preferences": {
    "communication_style": "casual"
  }
}
```

---

## Frequently Asked Questions

### Is my data really private?

**Yes.** Everything runs on your computer. Your conversations are stored in a folder on your machine (`Nola/Stimuli/conversations/`), not on any server.

### Do I need internet after setup?

**No.** Once installed, Nola works completely offline.

### How much does it cost?

**$0.** Nola is open source and free forever.

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

## What Can You Do With Nola?

| Use Case | Example |
|----------|---------|
| **Daily assistant** | "Remind me what we discussed yesterday" |
| **Project helper** | "Help me brainstorm features for TaskMaster" |
| **Learning buddy** | "Quiz me on the Python concepts we covered" |
| **Writing partner** | "Help me draft an email to my team" |

---

## Using Docker (Alternative Setup)

If you prefer containers:

```bash
# Make sure Ollama is running on your host machine first
ollama serve

# Then start the Docker containers
./start-docker.sh
```

---

## The Bigger Picture

Nola isn't just a chatbot — it's a **Cognitive Operating System** in development.

### What Makes This Different

| Standard AI | Nola |
|-------------|------|
| Stateless (forgets everything) | Persistent identity across sessions |
| Flat context (O(N²) noise) | Hierarchical attention (O(k·c²) signal) |
| Requires retraining to "learn" | Learns through experience, not weights |
| One-size-fits-all | Adapts to YOU over time |

### The Roadmap

See **[docs/ROADMAP.md](docs/ROADMAP.md)** for the full vision:
- ✅ **Now:** Subconscious, memory threads, HEA context levels
- 🔄 **Next:** Memory consolidation, philosophy constraints
- 🚀 **Future:** Reflex automation, dream states, multi-model routing, enterprise integration

---

## Looking for Collaborators

This is a solo project built since April 2025. The foundation is solid, the theory is proven, but with help it could move 10x faster.

**I'm looking for:**
- Python developers (async, state management)
- React developers (UI/UX improvements)
- AI researchers (cognitive architecture feedback)
- Backing (funding, partnerships, or just belief)

**Interested?** Open an issue, start a discussion, or reach out directly.

---

## Learn More

| Guide | Description |
|-------|-------------|
| [**Roadmap**](docs/ROADMAP.md) | Where this is going and how to help |
| [**Developer Guide**](DEVELOPERS.md) | Build features, understand the code |
| [**All Documentation**](docs/README.md) | Full documentation index |
| [**Architecture**](Nola/ARCHITECTURE.md) | Technical deep-dive |
| [**Contributing**](CONTRIBUTING.md) | Help make Nola better |

---

## Get Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/allee-ai/AI_OS/issues)
- **Discussions:** Share how you're using Nola

---

*Built with ❤️ by someone who believes AI should grow with you, not reset every conversation.*
