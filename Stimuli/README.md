# Stimuli

External inputs that flow into the agent's processing pipeline.

## Architecture

Config-driven integration layer. Add new API sources by dropping a YAML file.

```
Stimuli/
├── router.py          # Universal API adapter
├── sources/           # YAML configs for each platform
│   ├── _template.yaml # Copy this for new integrations
│   ├── gmail.yaml     # Email (OAuth2)
│   ├── slack.yaml     # Slack DMs/mentions
│   └── sms.yaml       # Twilio SMS
├── conversations/     # Historical logs
└── comms/             # Scratch/staging area
```

## Design Philosophy

**Deterministic vs Probabilistic Split:**

| Filled by Code | Filled by LLM |
|----------------|---------------|
| Authentication | Subject line |
| Routing (to/from) | Body content |
| Thread IDs | Tone/style |
| Timestamps | - |
| Sender profiles | - |

LLM only fills content slots. Everything else is derived from context.

**Push to Native Drafts:**

Responses go to platform's native draft folder (Gmail drafts, Slack scheduled messages). User reviews in familiar UI—no new interface needed.

## Quick Start

```python
from agent.Stimuli.router import get_router, ResponseTemplate

router = get_router()

# Pull from all enabled sources
messages = router.pull_all()

for msg in messages:
    print(f"From {msg.sender_name}: {msg.body[:50]}...")
    
    # Create response (LLM fills subject/body)
    response = ResponseTemplate(
        platform=msg.platform,
        to=msg.sender_id,
        to_name=msg.sender_name,
        thread_id=msg.thread_id,
        in_reply_to=msg.id,
        subject="Re: " + (msg.subject or ""),
        body="Your generated response here"
    )
    
    # Push to drafts
    router.push(msg.platform, response)
```

## Adding a New Source

1. Copy `sources/_template.yaml` → `sources/yourapi.yaml`
2. Fill in:
   - `auth`: How to authenticate (bearer, oauth2, api_key)
   - `pull.endpoint`: Where to fetch messages
   - `pull.mapping`: JSONPath to extract fields
   - `push.endpoint`: Where to send responses
   - `push.body_template`: Request body with `{{slots}}`
3. Set `enabled: true`
4. Restart to load

## NormalizedMessage Format

Every platform maps to:

```python
NormalizedMessage(
    platform="gmail",       # Source identifier
    id="abc123",           # Message ID
    thread_id="thread456", # Conversation thread
    sender_id="bob@x.com", # Sender identifier
    sender_name="Bob",     # Display name
    subject="Hello",       # Subject (if applicable)
    body="Message text",   # Content
    timestamp=datetime,    # When received
    raw={...}              # Original API response
)
```

## YAML Config Reference

```yaml
name: myapi           # Unique identifier
type: rest            # rest, imap, websocket
enabled: true
poll_interval: 300    # Seconds between pulls

auth:
  method: bearer      # bearer, oauth2, api_key, basic
  token_env: MY_TOKEN # Env var name

pull:
  endpoint: https://api.example.com/messages
  method: GET
  params:
    status: unread
  mapping:
    messages: "$.data"     # JSONPath to message array
    id: "$.id"
    thread_id: "$.thread"
    sender_id: "$.from"
    sender_name: "$.from_name"
    body: "$.content"

push:
  endpoint: https://api.example.com/drafts
  method: POST
  body_template:
    to: "{{to}}"
    subject: "{{subject}}"
    body: "{{body}}"
```

## Legacy Sources

- `conversations/` - Historical conversation logs
- `comms/` - Communication channels (email drafts, messages)

These predate the router and store raw files. May be migrated to SQLite.
