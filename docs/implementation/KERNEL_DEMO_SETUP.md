# Kernel Integration - "Living Body" Demo Setup

This guide will help you set up Nola to control a Kernel browser for your Wednesday demo.

## 🎯 Demo Goal

Type: **"hey nola do the facebook thing"**

Nola will:
1. ✅ Launch a Kernel browser (with Live View)
2. ✅ Navigate to a login page
3. ✅ Login with human-like behavior (mouse jerks, typing delays)
4. ✅ Generate post content from her identity/memory
5. ✅ Post with realistic typing patterns
6. ✅ Return the Live View URL so you can watch

---

## 🚀 Quick Setup (5 minutes)

### 1. Get Your Kernel API Key

```bash
# Visit https://app.onkernel.com and sign up
# Copy your API key from the dashboard
```

### 2. Configure Environment

```bash
# Copy example env file if you don't have one
cp .env.example .env

# Edit .env and add your Kernel API key
# KERNEL_API_KEY=your_key_here
```

### 3. Install Dependencies

```bash
cd Nola/react-chat-app/backend

# Install Kernel SDK and Playwright
pip install kernel playwright

# Install Playwright browsers (required)
playwright install chromium
```

### 4. Start the React Chat

```bash
# From the backend directory
python main.py

# In another terminal, start the frontend
cd ../frontend
npm install  # First time only
npm run dev
```

---

## 🎭 Demo Commands

Once your chat is running, try these:

### Launch the Full Demo
```
hey nola do the facebook thing
```

### Check Browser Status
```
browser status
```

### Close Session (saves identity)
```
close browser
```

---

## 🧠 How It Works

### Architecture Flow

```
You → React Chat → agent_service.py → kernel_service.py → Kernel API
                         ↓
                   Nola's Identity DB
                         ↓
                   Content Generation
```

### The "Human Behavior" Magic

**Mouse Jerks**: Random movements that mimic a stuck mouse ball
```python
# Random jerk to 800x600, then smooth move to target
await human_mouse_movement(target_x=450, target_y=300, add_jerk=True)
```

**Human Typing**: Variable delays, occasional typos
```python
# Types "Hello" with random 50-150ms delays
# 5% chance of typo → backspace → correction
await human_type("Hello world!", add_typos=True)
```

**Persistent Identity**: 
- Your Kernel profile saves cookies, logins, session state
- Linked to Nola's identity DB via `profile_name = "nola_identity"`
- Survives across sessions (12+ hour "living body")

---

## 📋 Pre-Demo Checklist

- [ ] Kernel API key configured in `.env`
- [ ] Dependencies installed: `pip install kernel playwright`
- [ ] Playwright browsers installed: `playwright install chromium`
- [ ] React chat running on http://localhost:5173
- [ ] Test command: "browser status" (should show no active session)
- [ ] Test demo: "do the facebook thing"
- [ ] Live View URL opens in browser (watch the automation!)

---

## 🎪 Wednesday Demo Script

### The Pitch
> "I've integrated Kernel's unikernel infrastructure as Nola's 'living body.' 
> My 7B model manages the browser through a persistent SQL control plane. 
> Watch - the agent never loses its task context because Kernel snapshots 
> the entire state between stimuli."

### The Show
1. Open React chat on left screen
2. Open Live View URL on right screen (after "do the facebook thing")
3. Type: **"hey nola do the facebook thing"**
4. Watch both screens:
   - Left: Nola's response with Live View link
   - Right: Browser automating with human-like behavior
5. Point out:
   - Mouse jerks (stuck ball simulation)
   - Typing delays and corrections
   - Content generated from identity DB

### The Closer
> "The browser persists its identity across sessions. When Nola 'wakes up' 
> in 12 hours, she's already logged in. No hallucination, no task drift - 
> just a 7B model with a body that doesn't decay."

---

## 🔧 Customization

### Change the Target Site

Edit [kernel_service.py](../Nola/services/kernel_service.py):

```python
# Line ~265
login_url = "https://httpbin.org/forms/post"  # Current test site

# Change to:
login_url = "https://your-test-site.com/login"
```

### Customize Post Content

Edit the `_generate_post_from_identity()` function in [agent_service.py](../Nola/services/agent_service.py):

```python
# Line ~503
# Pulls from Nola's identity: name, personality, interests
# Generates contextual post via agent.generate()
```

### Add Custom Commands

In `agent_service.py`, add to `_is_demo_command()`:

```python
custom_triggers = [
    "your custom trigger",
    "another trigger"
]
```

---

## 🐛 Troubleshooting

### "Kernel SDK not available"
```bash
pip install kernel playwright
playwright install chromium
```

### "KERNEL_API_KEY not found"
Check your `.env` file in the project root:
```bash
cat .env | grep KERNEL_API_KEY
```

### "Browser failed to launch"
Check Kernel dashboard for:
- API key validity
- Account status
- Free credits remaining ($5/month free tier)

### Live View not loading
- Ensure `headless=False` in `launch_browser()` call
- Check firewall/network allows websocket connections
- Verify you're using the full URL (starts with `https://`)

---

## 📚 Additional Resources

- **Kernel Docs**: https://onkernel.com/docs
- **Kernel Playground**: https://app.onkernel.com/playground
- **Computer Controls**: https://onkernel.com/blog/announcing-computer-controls-api
- **Pricing**: https://onkernel.com/docs/info/pricing

---

## 💡 What's Next?

After the demo, you can:

1. **Connect Real Credentials**: Store Facebook/LinkedIn credentials in identity DB
2. **Add Site-Specific Workflows**: Create custom navigation flows per site
3. **Integrate with Subconscious**: Trigger browser actions from learned patterns
4. **12-Hour Loops**: Schedule periodic wake-ups via consolidation daemon
5. **Multi-Identity Profiles**: Different Kernel profiles for different personas

---

## 🎉 You're Ready!

Your 7B model now has a persistent body in the cloud. Go show Union Hall what cognitive OS means!

**Demo Date**: Wednesday, January 8, 2026  
**Location**: Union Hall (1311 Vine St), 5:30 PM  
**What to Bring**: This working demo 🚀
