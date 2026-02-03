# AI OS — A Cognitive Architecture for Local LLMs

**An open-source framework for building personal AI that remembers you. Private. Free. Early.**

> **Active Development** — The core agent capabilities work, the modules are scaffolded and a lot of the work that would really make this great is copy paste coding. adding endpoints for things we already use, integrating calendar, etc. Looking for collaborators at any level, and also we respect ideas from non technical users. Key Point I wont burn out because i love this work but Id love even more to see its growth accelerated by even just a few people.

![CI](https://github.com/allee-ai/AI_OS/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-AGPL-blue.svg)

---

<details>
<summary><strong>A Quick Human Note</strong> (click to expand)</summary>

I loved building this.

It's been almost obsessive for close to a year. When I started, I knew a lot of math and quite a bit of psychology, and I'd heard the term neuroscience like six times, so obviously I knew it inside and out. I digress. Moving on.

Initially, the project started because everybody LOVED GPT-4o, so I had to check it out, and I LOVED it too. It was a great thought partner. It made stuff up all the time, but it was cool to be able to rapidly iterate over a theory with a partner who always told me I was the queen of everything. No ego boost needed because I'm awesome.

I wanted to get ChatGPT and Siri to be best buds and work together. So I'd tell ChatGPT to be Siri and do Siri things, and it would. Solved AGI right then and there. Just kidding.

It would pretend to do things, and I would want to throw my phone out the window, because parsing an LLM output is like trying to understand someone else's toddler. You can do it… eventually. Mostly you just nod and smile and say, "Okay dear, let's try again." No fluffing.

So I started trying to give GPT-3.5 function calling abilities. I set up a Pythonista endpoint and used CLI and the Openai key to talk to 3.5, and I just always said execution is called by saying "execute:function_name".

Mind you, this is a side project I'm doing on my phone in the bathroom at work, so it was slow going. But eventually I got it to mostly work. Then the API broke. I gave up.

And this is what's left.

An entire operating system for LLMs that just takes ALLLL the things we EXPECT them to do and makes them do that. But all of it is visible. Complicated terms like forward pass are not present, but you can look at subconscious in the repo and see that it's a scientifically accurate description of the programs module, and also it's a CoT dashboard where you can save things you've already done.

Form is a tool builder. Log keeps track of stuff. Identity and philosophy are just editable profiles. But the deeper research architecture fascinates me.

I built this because I desperately want it, and I desperately want everyone to have it, because I think if AI made people better, it wouldn't take their jobs. Simple concept. Massive implications.

If you read this, I appreciate it. Please enjoy whatever it is you do with my bathroom project :)

— Allee

</details>

---

## What is AI OS?

LLMs are powerful but unreliable. They hallucinate, forget, lose track of who they are, and treat every conversation like it's the first.

AI OS is an architecture layer that wraps your local LLM and handles what models are bad at:

- **Memory** — Persistent across sessions, organized by relevance 
- **Identity** — Consistent personality stored structurally 
- **Learning** — Extracts facts from conversations 
- **Control** — LLM handles language; OS handles state 
- **Background Loops** — Predefined COT for specific workflows

**The pain point we solve:** These pieces exist separately — RAG libraries, prompt templates, memory plugins, identity frameworks — but nowhere in one integrated package for local LLMs. AI OS is that package.

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

**On Mac/Linux:**
1. Open Terminal (on Mac: search "Terminal" in Spotlight)
2. Navigate to the downloaded folder:
   ```bash
   cd ~/Downloads/AI_OS
   ```
3. Run the start script:
   ```bash
   bash scripts/start.sh
   ```

**On Windows:**
- Double-click `run.bat` in the downloaded folder.

The script handles everything:
- Installs the LLM runtime (Ollama)
- Starts the OS backend and chat interface
- Opens your browser automatically

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

**The LLM doesnt't remember that. The OS did.** Your facts live in a database, organized by relevance, retrieved when needed. The LLM just turns that context into natural language.

---

## Make It Yours

### Configure in the UI

Everything is configurable directly from the dashboard.

1.  **Customize Your Agent:** Click the **Agent Card** on the home screen to change its name, personality, and greeting (e.g., "Atlas", "Vega", or "Sarcastic Robot").
2.  **Manage Identities:** Click **Identity** to update your profile.
    *   **Automatic Setup:** Your primary user and machine ID profiles are pre-created.
    *   **Family & Trust:** Add family members and assign trust levels.
    *   **Context Awareness:** If a family member says hello, the Agent remembers them and understands their relationship to you.
3.  **Create Tools:** Navigate to **Agent → Form** to build custom web tools or edit existing capabilities using the simple form generator.

It's prompt engineering, but organized. You define who you (and your agent) are, and the OS handles the context window.

---

## Frequently Asked Questions

### Is my data really private?

**Yes.** Everything runs on your computer. Your conversations, memories, and profile are stored locally in SQLite, not on any server.

### Do I need internet after setup?

**No.** Once installed, AI OS works completely offline.

### How much does it cost?

**$0.** Open source, AGPL licensed, free forever.

### What computer specs do I need?

| | Minimum | Recommended |
|---|---------|-------------|
| RAM | 8GB | 16GB |
| Storage | 8GB free | 15GB free |
| OS | macOS 10.15+, Windows 10+, Ubuntu 20.04+ | Same |

### Can I use a different AI model?

**Yes!** You can switch chat models instantly.

*   **Chat Models:** Use the model selector in the chat interface to switch between models or click **"Add Model"** to download new ones (like Llama 3, Phi-3, Mistral). The AI OS architecture works with any model you choose for conversation. 
*   **Import History:** Click **Import**, choose your export type, and port your conversations from other models directly into AI OS.

> **Pro Tip for Developers:** You can override the system architecture models by editing the `.env` file if you want to experiment with different backends for specific modules.

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
| **Action** | Locked in chat box | Tool framework ready, integrations planned |
| **Learning** | Same quality forever | Extracts and stores facts from conversations |

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
- **Now:** Subconscious, memory threads, HEA context levels
- **Next:** Memory consolidation, philosophy constraints
- **Future:** Reflex automation, dream states, multi-model routing, enterprise integration

---

## Help Build This

Built solo since April 2025. The foundation works. Now it needs a community.

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
| [**Architecture**](docs/ARCHITECTURE.md) | Technical deep-dive (threads, HEA, state) |
| [**Research Paper**](docs/RESEARCH_PAPER.md) | The theory behind the design |
| [**Contributing**](CONTRIBUTING.md) | How to help build it |

---

## Get Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/allee-ai/AI_OS/issues)

- **Discussions:** Share how you're using Agent

---

## Built With & Thanks To

AI OS stands on the shoulders of giants. Deep gratitude to the tools, models, and communities that make this possible:

### 🦙 Runtime & Models

| | What | How It Powers AI OS |
|---|------|---------------------|
| [**Ollama**](https://ollama.ai) | Local LLM runtime | The engine. One-click model downloads, fast inference, no cloud required. AI OS wouldn't exist without Ollama making local LLMs accessible. |
| [**Llama**](https://llama.meta.com) (Meta) | Open-weight foundation models | The voice. Llama 2/3 models are the default conversational backbone. Meta's decision to open-source changed everything. |
| [**Qwen**](https://qwenlm.github.io) (Alibaba) | Efficient multilingual models | Fast local option. Qwen 2 1.5B runs great on laptops for quick responses. |
| [**Mistral**](https://mistral.ai) | High-quality open models | Power option. Mistral 7B punches way above its weight for complex reasoning. |
| [**Phi**](https://huggingface.co/microsoft/phi-2) (Microsoft) | Small but mighty models | Efficiency research. Phi models prove small can be smart. |
| [**nomic-embed-text**](https://www.nomic.ai) | Open embedding model | The glue. Powers semantic search and concept similarity scoring. |

### Development Partners

| | What | How They Helped |
|---|------|----------------|
| [**Claude**](https://anthropic.com) (Anthropic) | Advanced reasoning model | Pair programming. Claude helped implement the thread system and debug async loops. Great at explaining why code doesn't work. |
| [**GPT-4/5**](https://openai.com) (OpenAI) | Frontier AI models | Pair programming. GPT helped with FastAPI patterns and React component structure. |
| [**Gemini**](https://deepmind.google/technologies/gemini/) (Google) | Multimodal AI | UX review. Gemini audited the UI and identified features that existed in backend but weren't exposed to users. |

### 💻 Development Environment

| | What | How We Use It |
|---|------|---------------|
| [**VS Code**](https://code.visualstudio.com) | Open-source editor | The workshop. All AI OS development happens here. |
| [**GitHub Copilot**](https://github.com/features/copilot) | AI pair programmer | Tool builder. Copilot accelerates Form thread development — use it to build your own AI OS tools. |
| [**Cursor**](https://cursor.sh) | AI-native IDE | Deep integration. Agent-assisted refactoring and architecture work. |

### 🔧 Infrastructure

| | What | Role |
|---|------|------|
| [**FastAPI**](https://fastapi.tiangolo.com) | Python web framework | Backend API — async, typed, fast |
| [**React**](https://react.dev) | UI framework | Frontend — responsive, component-based |
| [**Three.js**](https://threejs.org) | 3D graphics | Concept graph visualization |
| [**SQLite**](https://sqlite.org) | Embedded database | All state storage — portable, no server |
| [**uv**](https://github.com/astral-sh/uv) | Fast Python package manager | Dependency management — 10-100x faster than pip |

###  Community & Research

| | Contribution |
|---|--------------|
| [**Hugging Face**](https://huggingface.co) | Model hub, transformers library, community |
| [**r/LocalLLaMA**](https://reddit.com/r/LocalLLaMA) | Local AI community, testing, feedback |
| [**LangChain**](https://langchain.com) | Patterns for LLM applications (we diverge but learned from) |
| **Cognitive Science Literature** | Hebbian learning, spread activation, episodic memory research |

###  Theoretical Foundations

**Nothing here is new.** AI OS applies well-established cognitive science to LLM context management. The bet is that these proven patterns transfer usefully to AI systems — but that's a hypothesis under testing, not a claim.

| Research | What It Proved | How AI OS Applies It |
|----------|----------------|---------------------|
| **Hebbian Learning** (Hebb, 1949) | "Neurons that fire together, wire together" | Concepts accessed together get stronger links. Established neuroscience. |
| **Spread Activation** (Collins & Loftus, 1975) | Memory retrieval follows associative paths | Related concepts activate when one is accessed. Textbook cognitive psych. |
| **Working Memory** (Baddeley, 1986) | Attention has hierarchical capacity limits | L1/L2/L3 token budgets mirror proven memory architecture. |

**What needs testing:** Whether these patterns actually improve LLM coherence over long interactions. We have anecdotal evidence (it *feels* better), not rigorous benchmarks yet. Help us build those.

### 🤝 Missing Something?

If we're using your work and didn't credit it properly, or if you want to collaborate:

**Open a Discussion or reach out.** We're trying to build in the open and credit accurately.

---

## License

AGPL — Use it, fork it, build on it. Just don't claim you wrote it from scratch.

---

*Your LLM is powerful. It just needs a brain.*
