# Site Migration Runbook — GitHub Pages → Caddy on AI_OS droplet

Source of truth for the multi-apex migration. Stack discovered May 5 2026:
**Caddy v2.11.2** on Ubuntu 24.04 droplet (`Nola`, `24.144.115.72`).

> Caddy ≠ nginx. The original plan was nginx-shaped; this runbook is Caddy-shaped.
> Auto-HTTPS via Let's Encrypt is built in — **no certbot**. New domain = 3 lines
> of Caddyfile + DNS A record + rsync.

---

## Current droplet state (snapshot — re-verify before acting)

| Layer | What's there |
|-------|--------------|
| Web server | Caddy v2.11.2, listening on `:80` and `:443` |
| Caddyfile | `/etc/caddy/Caddyfile` — one site block for `24-144-115-72.sslip.io` reverse-proxying `127.0.0.1:8001` |
| AI_OS demo backend | uvicorn on `127.0.0.1:8001` (proxied) |
| Other process on :8000 | uvicorn bound to `0.0.0.0:8000` serving the Nola frontend — **publicly exposed**, see security note |
| Local LLM | ollama on `127.0.0.1:11434` (loopback only) |
| Disk | 33 GB total, 16 GB free |
| Firewall | **ufw inactive** — see security note |
| `/var/www/aios` | exists, root-owned, currently empty/unused |
| Cert store | Caddy-managed at `/var/lib/caddy/.local/share/caddy/` |
| OS | Ubuntu 24.04.3 LTS |

---

## Onboarding a new apex domain (the canonical recipe)

For each domain (`allee-ai.com`, `bycade.com`, `vanguard-reconstruction.com`, …):

### 1. Register & DNS (Cade present at Namecheap)

| Type | Host | Value             | TTL |
|------|------|-------------------|-----|
| A    | `@`  | `24.144.115.72`   | 300 |
| A    | `www`| `24.144.115.72`   | 300 |

Delete any GitHub Pages CNAME on `www` and apex A records pointing at `185.199.x.x`.

### 2. Provision directory on droplet

```bash
ssh AIOS
DOMAIN=allee-ai.com
sudo mkdir -p /var/www/$DOMAIN/public
sudo chown -R $USER:caddy /var/www/$DOMAIN
sudo chmod 755 /var/www/$DOMAIN /var/www/$DOMAIN/public
```

### 3. Add site block to `/etc/caddy/Caddyfile`

Copy [`infra/Caddyfile.site.template`](Caddyfile.site.template), substitute `<DOMAIN>`, append to droplet's Caddyfile (do NOT replace the existing sslip block).

```bash
# on droplet
sudo nano /etc/caddy/Caddyfile  # paste template, replace <DOMAIN>
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

Caddy will issue a Let's Encrypt cert on the first HTTPS request to that hostname. First request may take 5–15 s while the cert is fetched.

### 4. Deploy site files (from laptop)

```bash
./infra/deploy_site.sh allee-ai.com workspace/allee-ai.github.io
```

### 5. Verify

```bash
# Before DNS propagation (or for sanity)
curl -sI -H "Host: allee-ai.com" http://24.144.115.72/ | head -5

# After DNS propagation
dig +short allee-ai.com @1.1.1.1   # → 24.144.115.72
curl -sI https://allee-ai.com/     # → 200, valid LE cert
```

In browser, walk the page tree:
- [ ] Homepage renders
- [ ] All `learn-*.html`
- [ ] `services.csv`, `products.csv` load (Network tab, 200, text/csv)
- [ ] `mobile-demo-app.html` registers `mobile-demo-sw.js` (Application → Service Workers)
- [ ] iframe in `aios.html` loads `https://24-144-115-72.sslip.io/` cleanly
- [ ] No mixed-content warnings

---

## First-domain migration (allee-ai.com)

Order matters — minimize downtime:

1. **T-24h**: lower Namecheap TTL on existing GitHub Pages records to 300 s. Don't change values yet.
2. Run steps 2 + 3 above (provision dir, add Caddy block).
3. Run step 4 (deploy via rsync).
4. Run step 5 with the Host-header curl — fix any 404 BEFORE cutover.
5. Cut DNS at Namecheap (delete GH Pages records, add A → 24.144.115.72 for `@` and `www`).
6. Wait ≤5 min, verify with browser. Caddy fetches cert on first request.
7. **Do NOT archive the GitHub Pages repo for 48 h.** That's your rollback (§Rollback).
8. After 48 h stable: archive GH repo, disable Pages.

---

## Adding subsequent domains (bycade.com, vanguard-*)

Skip the cutover dance — these are new domains, no live site to lose.

1. Register at Namecheap, set A records → droplet IP.
2. Provision dir, add Caddyfile block, reload Caddy.
3. Deploy site files via `deploy_site.sh`.
4. Visit `https://<domain>/`. Caddy fetches cert. Done.

Total wall time per new domain: ~10 min, almost all of it waiting for DNS propagation.

---

## Rollback (allee-ai.com only — the others have no rollback because no prior site)

If cutover breaks within minutes:

1. **Namecheap**: replace droplet A records with GitHub Pages canonical values:
   - `A @ 185.199.108.153`, `A @ 185.199.109.153`, `A @ 185.199.110.153`, `A @ 185.199.111.153`
   - `CNAME www <user>.github.io`
   - **Verify current GH Pages IPs at https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site BEFORE starting** — record them in this runbook before cutover.
2. GitHub: ensure repo is not archived; verify Pages is still enabled.
3. Wait 5 min for TTL.

If Caddy config breaks (validate fails, won't reload):
```bash
sudo cp /etc/caddy/Caddyfile.bak.<date> /etc/caddy/Caddyfile
sudo systemctl reload caddy
```
**Always `cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak.$(date +%F)` before editing.**

---

## Risks (top 3)

1. **Caddyfile syntax error breaks ALL sites including the sslip demo.** A single missing brace takes everything down. Mitigation: always `caddy validate` before `systemctl reload`. Backup the Caddyfile first.
2. **Cert issuance fails** because DNS hasn't propagated, or LE rate limit hit (5 certs/week per registered domain). Mitigation: confirm `dig +short <domain>` returns droplet IP from `1.1.1.1` BEFORE first HTTPS request. Don't loop on cert issuance during testing — Caddy will back off automatically.
3. **Single point of failure** — droplet dies → all sites + AI_OS demo die together. Mitigation: enable DigitalOcean weekly snapshots ($1.20/mo) BEFORE migration. Source-of-truth lives in git on laptop; rebuild path is documented in this runbook.

---

## Out of scope (filed separately)

- ufw enablement + firewalling :8000 (security goal)
- ollama disposition (decision: keep / move / decommission)
- Cloudflare/CDN in front of Caddy
- Multi-droplet HA
- Email / MX records
- Monitoring / uptime alerts

---

## Decision: where does the AI_OS demo live?

**Stay at `https://24-144-115-72.sslip.io/`. Do NOT move to `demo.allee-ai.com`.**

Reasons:
- sslip's wildcard cert is automatic; subdomain cert is one more thing to manage.
- Decouples demo backend from marketing domain — if you swap the demo, no DNS work.
- The iframe in `aios.html` already targets sslip; no CSP/CORS rework.

Revisit only if the sslip URL becomes a credibility issue with prospective users.
