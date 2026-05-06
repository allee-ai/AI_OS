# Form-server deployment plan (next session)

The form-server (`infra/form_server.py`) is verified working locally. Routes
- vanguard-reconstruction.com → allee@allee-ai.com
- vanguard-relocations.com   → assistant@allee-ai.com
- allee-ai.com               → allee@allee-ai.com (default)

5 successful test emails sent through Proton Bridge in this session.

## Production architecture

```
Visitor → https://vanguard-reconstruction.com/contact-submit (POST form)
       → Caddy on droplet matches /contact-submit
       → reverse_proxy 127.0.0.1:8042
       → SSH reverse tunnel (Mac → droplet)
       → form-server on Mac (this codebase, infra/form_server.py)
       → SMTP 127.0.0.1:1025 (Proton Bridge on Mac)
       → email lands in destination Proton inbox
```

## Three pieces to wire (deploy order)

### 1. launchd plist: keep form-server running on Mac

`~/Library/LaunchAgents/com.allee.form-server.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.allee.form-server</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/cade/Desktop/AI_OS/.venv/bin/python</string>
    <string>/Users/cade/Desktop/AI_OS/infra/form_server.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/cade/Library/Logs/form-server.out</string>
  <key>StandardErrorPath</key><string>/Users/cade/Library/Logs/form-server.err</string>
</dict>
</plist>
```
Load: `launchctl load ~/Library/LaunchAgents/com.allee.form-server.plist`

### 2. launchd plist: persistent reverse SSH tunnel

`~/Library/LaunchAgents/com.allee.form-tunnel.plist`:
```xml
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/ssh</string>
  <string>-N</string>
  <string>-o</string><string>ServerAliveInterval=30</string>
  <string>-o</string><string>ServerAliveCountMax=3</string>
  <string>-o</string><string>ExitOnForwardFailure=yes</string>
  <string>-R</string><string>127.0.0.1:8042:127.0.0.1:8042</string>
  <string>AIOS</string>
</array>
<key>KeepAlive</key><true/>
```
Droplet `/etc/ssh/sshd_config` needs `GatewayPorts clientspecified` (already?
check before deploy).

### 3. Caddy on droplet — add handle to BOTH site blocks

In `/etc/caddy/Caddyfile`, inside `vanguard-reconstruction.com, www.vanguard-reconstruction.com {` block AND inside `vanguard-relocations.com, www.vanguard-relocations.com {` block, add **before** `try_files`:
```caddy
handle /contact-submit {
    reverse_proxy 127.0.0.1:8042
}
```
Then `caddy validate` + `systemctl reload caddy`.

## Checks before going live

- [ ] launchd jobs both `Loaded` (`launchctl list | grep allee`)
- [ ] `curl http://127.0.0.1:8042/health` returns ok
- [ ] On droplet: `curl http://127.0.0.1:8042/health` works (tunnel up)
- [ ] On droplet: `caddy validate` clean
- [ ] Form submit from public URL lands in inbox
- [ ] Sleep Mac → form returns 502 (expected) → wake → form recovers

## Risk: bridge password rotation

Proton Bridge sometimes regenerates its app password (we already saw "no such
user" failures in `sensory_feeds`). When that happens, update keychain:
```
security add-generic-password -s 'AIOS-Proton-Bridge' \
  -a 'alleeroden@pm.me' -w '<NEW_PW>' -U
```
Form-server reads keychain on every request, so no restart needed.

## Pieces NOT YET committed/pushed at session end

- `workspace/vanguard-reconstruction/contact.html` has the contact form (action="/contact-submit")
- `Vanguard-Relocations/frontend/pages/services.html` has the contact form
- Both will 404 on submit until Caddy `handle /contact-submit` is added on droplet
- DON'T deploy via `infra/deploy_site.sh` until tunnel + Caddy are wired

## What's safe to do without the tunnel

- Push the form HTML to the GH Pages preview (`allee-ai.com/reconstruction/`) — it'll
  show the form but submit will 404. Acceptable for visual review.
- Cade can preview locally via `python3 -m http.server` in either site dir; submit
  will still 404 unless she runs `python infra/form_server.py` and edits the form
  `action` to `http://127.0.0.1:8042/contact-submit`.
