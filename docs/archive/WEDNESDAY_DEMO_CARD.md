# 🎪 WEDNESDAY DEMO - QUICK REFERENCE

**Date**: January 8, 2026 | **Time**: 5:30 PM | **Location**: Union Hall (1311 Vine St)

---

## 🎯 THE DEMO LINE

**"Hey Nola, do the facebook thing"**

Then watch both screens:
- **Left**: React chat with Nola's response
- **Right**: Live browser view with human-like automation

---

## 🎤 THE PITCH (30 seconds)

> "I'm building AI_OS - a cognitive operating system that gives agents persistent memory and identity. The problem? Agents crash, drift, and forget. The solution? I've integrated Kernel's unikernel runtime as a 'living body' that never decays. My 7B model manages browser sessions through a SQL control plane, maintaining task gravity across 12-hour horizons. Watch."

---

## 🎬 THE DEMO FLOW

1. **Show the setup** (5 sec)
   - React chat on left
   - Terminal showing backend running

2. **Execute command** (2 sec)
   - Type: "hey nola do the facebook thing"
   - Hit enter

3. **Point out the response** (10 sec)
   - Live View URL appears
   - Session ID shown
   - Generated post content visible

4. **Open Live View** (15 sec)
   - Click the URL
   - Browser opens in new tab
   - Point out it's running remotely

5. **Narrate the behavior** (30 sec)
   - "Watch the mouse - see that jerk? That's human behavior mimicry"
   - "The typing has variable delays - 50-150ms between keys"
   - "5% chance of typo with backspace correction"
   - "All running in a Kernel unikernel with <20ms cold starts"

6. **The closer** (15 sec)
   - "This browser maintains state for 12+ hours"
   - "Costs pennies because of intelligent standby"
   - "My 7B model generates the content from identity DB"
   - "It's the first 'living' runtime I've seen that actually works"

---

## 🔑 KEY TECHNICAL POINTS

When they ask technical questions:

### "How does it work?"
- Kernel provides unikernel-based browser VMs
- Playwright CDP for programmatic control
- Computer Controls API for OS-level mouse/keyboard
- Persistent profiles linked to SQL identity DB

### "What makes it human-like?"
- Random mouse jerks (stuck ball simulation)
- Variable keystroke timing (50-150ms)
- Typo injection + correction (5% rate)
- Hover events and spatial navigation

### "Why not just use Selenium?"
- Selenium gets banned by bot detection
- No persistent state across sessions
- Heavy Docker/VM overhead
- Kernel: <20ms startup, persistent identity, stealth mode

### "What's the cost?"
- $5/month free tier (more than enough for dev)
- $0.000016 per GB-second
- Intelligent standby = only pay when active
- 12-hour session costs ~$0.01

### "How does memory work?"
- Identity stored in SQLite (owned space)
- Kernel profile saves cookies/logins (cloud space)
- Agent generates content from identity context
- Consolidation daemon learns from interactions

---

## 🚨 BACKUP PLANS

### If Live View doesn't load:
- Show the terminal output (browser launched)
- Walk through the code in kernel_service.py
- Explain: "In production this always works, might be wifi here"

### If Kernel API is down:
- Show the integration code
- Walk through the architecture diagram
- Pivot to: "Let me show you the identity system instead"

### If crowd is skeptical:
- "I know it sounds wild, but watch the Live View URL"
- "This is running on their servers right now, not my laptop"
- "Here's their pricing page - it's real infrastructure"

---

## 💪 CONFIDENCE BOOSTERS

**You've built**:
- ✅ Full integration with production Kernel API
- ✅ Human behavior mimicry (mouse jerks, typing)
- ✅ Identity-driven content generation
- ✅ Persistent profile management
- ✅ Working chat interface with demo commands

**You know**:
- ✅ The tech stack (Unikraft, CDP, MCP)
- ✅ The pricing model (GB-seconds, standby mode)
- ✅ The competitive advantage (vs Selenium/Docker)
- ✅ Your research angle (cognitive OS, sovereignty)

**You're ready**.

---

## 📱 LAST-MINUTE CHECKLIST

- [ ] Laptop charged (bring charger)
- [ ] Kernel API key in `.env` file
- [ ] Test "do the facebook thing" before leaving
- [ ] Backend running: `cd Nola/react-chat-app/backend && python main.py`
- [ ] Frontend running: `cd frontend && npm run dev`
- [ ] Browser open to http://localhost:5173
- [ ] Backup: Screenshot of successful demo on phone
- [ ] Business cards (if you have them)
- [ ] This reference card printed or on phone

---

## 🎊 POST-DEMO FOLLOW-UP

If they're interested:

**Next steps you can offer**:
1. "I can share the GitHub - it's all open source"
2. "Want to see the 12-hour loop implementation?"
3. "I'm building this as part of a cognitive OS paper"
4. "Here's how you'd integrate with your agent"

**What to ask them**:
1. "What use cases do you see for persistent browser agents?"
2. "Any interest in collaborating on the identity layer?"
3. "I'm looking for compute partners - open to chat?"

**Contact exchange**:
- Get their email/LinkedIn
- Offer to send the demo code
- Mention Wednesday night is about networking, follow up Thursday

---

## 🔥 THE CLOSER LINE

> "This is a 7B model managing a body that persists across time. 
> It's not just automation - it's the first step toward true agent sovereignty.
> And it runs on $5/month. Imagine what a 405B model could do with this."

**Then smile and wait for their reaction.**

---

**You got this. 🚀**
