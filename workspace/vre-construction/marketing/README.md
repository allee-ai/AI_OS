# Marketing assets — Vanguard Reconstruction

> All files in this folder are **internal drafts**. They are excluded from the
> public site via `robots.txt` and from the sitemap. Sub all `[YOUR CELL]`,
> `[X]`/`[Y]` price placeholders, and `[NUMBER]` license fields before
> publishing anything.

## What's here

| File | Purpose | Where it goes |
|---|---|---|
| `google-business-profile.md` | Paste-ready GBP listing copy — name, categories, service area, descriptions, services, Q&A, weekly posts, photo shot list | business.google.com |
| `social-posts.md` | Facebook, Nextdoor, Instagram, LinkedIn post drafts + 30-day cadence | Respective platforms |
| `email-templates.md` | Signature, cold outreach, quote follow-up, review ask, referral ask, out-of-scope referral | Mail client |
| `flyer.html` | Printable letter-size flyer (open in browser → Print → Save as PDF / print on cardstock) | Door-hangers, hardware stores, lockboxes at properties |

## Publish order (recommended for the first week)

1. **Day 1 — GBP listing.** Highest-leverage asset. Even at 0 reviews, the
   listing puts you in Maps for "electrician near me" Cincinnati searches.
2. **Day 1 — Facebook page + intro post.** Quick to stand up. Use the Day 1
   block in `social-posts.md`.
3. **Day 2 — Nextdoor in your home neighborhood.** Personal, name-the-street
   tone. Use the Hyde Park / Oakley template as a base.
4. **Day 2 — print 50 flyers.** Drop at landlord supply houses, hardware
   stores, neighborhood coffee shops with bulletin boards. Pin one in any
   property you finish work at (with owner's OK).
5. **Day 3–4 — landlord Facebook groups.** Use the FPE / Zinsco insurance
   post. Don't blast — one group per day, engage in comments.
6. **Day 5 — LinkedIn investor-angle post.** Long-form authority signal.
7. **Day 7 — first weekly GBP post.** Set a calendar reminder; Google
   rewards weekly activity.

## Tracking

Tag the website URL in each channel so you know what's working:

| Channel | URL to use |
|---|---|
| GBP | `https://vre-construction.com/?utm_source=gbp` |
| Facebook page | `https://vre-construction.com/?utm_source=fb_page` |
| Facebook groups | `https://vre-construction.com/?utm_source=fb_group` |
| Nextdoor | `https://vre-construction.com/?utm_source=nextdoor` |
| LinkedIn | `https://vre-construction.com/?utm_source=linkedin` |
| Flyer | `https://vre-construction.com/?utm_source=flyer` |
| Email signature | `https://vre-construction.com/?utm_source=email` |

After 30 days, look at which `utm_source` shows up most in the Caddy access
log (or whatever analytics you bolt on next) — those are the channels worth
doubling on.

## Before publishing — fill these in

- `[YOUR CELL]` — across all marketing files
- `[X]` / `[Y]` price bands — in flyer.html and sales/investor-onepager.md
- `[NUMBER]` Ohio EL license — in flyer.html footer
- `[Neighborhood]` / `[year]` / `[total]` — sample-job placeholders in
  sales/investor-onepager.md
- GBP review link — once GBP is live, paste into `email-templates.md` review
  request

A `grep -rEn "\[X\]|\[Y\]|\[YOUR CELL\]|\[NUMBER\]|\[Neighborhood\]"` across
`workspace/vre-construction/` will list everything still pending before you
hit publish.
