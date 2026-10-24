---
id: sitelink-diversity
title: Sitelink copy diversity across campaigns
tags: sitelinks, assets, ad strength, ctr, routes, diversity
priority: high
updated: 2026-10-23
---

# Sitelink diversity

## How critical is identical sitelink copy?

| Factor | Impact | Notes |
|--------|--------|--------|
| **Count** of ENABLED sitelinks on the campaign | **High** for Ad Strength | Google tip “Add N more sitelinks” — aim **≥6**, prefer **≥8–9** |
| Unique `link_text` **within** one campaign | **Medium** | Duplicate labels waste slots; each sitelink should be a distinct CTA |
| **Same** sitelink texts across many campaigns | **Low for Ad Strength** | Rating is per RSA + assets on that campaign. Sharing the same 6 labels across themes does **not** by itself keep ads on Average |
| Themed / varied descriptions + labels | **Medium for CTR & relevance** | Airport vs city vs holiday searchers should see matching extension copy |
| Random reshuffling of the same ideas | **Low / noise** | Prefer **thematic variants**, not random synonyms for the sake of difference |

Identical sitelinks across campaigns hurt relevance/CTR more than Ad Strength. Same destination URLs are fine; **vary `link_text` + description1/2** per campaign theme.

## Rules

1. Keep **stable final URLs** (book, fleet, routes, contact, faq, about — HTTP 200).
2. Per campaign, write **distinct** link texts (≤25) and **both** descriptions (≤35) — no empty desc pairs.
3. Theme the copy to the campaign (city routes, airport pickup, holiday resorts, EN cross-border, and so on).
4. Do **not** paste one identical pack onto every campaign in the same language.
5. Prefer **new assets per campaign** (or update that campaign’s own `asset_id`s). A shared asset update is not campaign-local.
6. After RSA rewrites, if `action_items` still asks for more sitelinks → **add** more (to 8–9), don’t only rename.

When creating a new themed campaign, clone sitelink structure from `get_campaign_assets` on a similar campaign, then rewrite labels/descriptions.

Cite **`sitelink-diversity`** + **`rsa-ad-strength`**.
