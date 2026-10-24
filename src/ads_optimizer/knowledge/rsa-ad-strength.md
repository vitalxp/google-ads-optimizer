---
id: rsa-ad-strength
title: Ad Strength (Good/Excellent) — density, semantic diversity & RSA rules
tags: rsa, ad strength, quality, poor, creatives, headlines, keyword density, semantic diversity, routes, get_creatives
priority: critical
updated: 2026-08-16
---

# Ad Strength (Сила объявления)

Source of truth for RSA create/edit. Based on Google Ads Help:
[About Ad Strength](https://support.google.com/google-ads/answer/9921843),
[RSA best practices](https://support.google.com/google-ads/answer/6167122),
[Write compelling ad copy](https://support.google.com/google-ads/answer/6167101).

**Ad Strength** = Incomplete / Poor / Average / **Good** / **Excellent**.  
It measures how well creative **matches ad group keywords** + asset **quantity and semantic diversity** — **not** Ad Rank / QS / auction win.

Target: every RSA we create or edit should aim for **Good or Excellent**.

---

## HARD RULE — always read Google `action_items` first

When fixing Ad Strength (POOR / INCOMPLETE / **AVERAGE** / any improve-RSA request):

1. Call `get_ad_strength` and/or `get_creatives` and **read every `action_items` string** Google returned for that ad.
2. **Do not ignore** a single recommendation even if every ad shows the same one.
3. Map recommendations → tools **before** rewriting RSA text:

| Google `action_items` (examples) | What to do |
|----------------------------------|------------|
| **Add N more sitelinks…** | `get_campaign_assets(campaign_id)` → if ENABLED sitelinks < 6 (prefer **≥8–9**), add via `add_sitelinks`. Confirm flow. |
| Include more keywords in headlines / descriptions | `get_keywords(ad_group_id)` → rewrite H/D with **Keyword density** + **Semantic diversity** → `update_responsive_search_ad` |
| Add more unique assets | Fill to **15 H / 4 D** with **different meaning categories** (not synonym swaps) |
| Unpin assets | Update RSA without pins (this app clears pins on update) |
| Incomplete / missing URL / keywords | Fix structure: final URL, keywords in ad group |

**Two common AVERAGE traps in this account:**

1. **Sitelinks tip only** while H/D are already 15/4 → fix sitelinks (often need 6→9), do not only rewrite headlines.
2. **No sitelink tip / keyword tip**, but H/D look “full” → usually **synonym stacking** (see below). Rewrite with the **balanced headline pool**.

4. After asset fixes, re-check `get_ad_strength` (rating may stay PENDING for hours; PAUSED campaigns recalculate slower).

---

## HARD RULE — always load this article

Before any `create_responsive_search_ad`, `create_ad_group_with_rsa`, `create_full_search_setup`, or `update_responsive_search_ad`:

1. `get_knowledge("rsa-ad-strength")` (or already cite it).
2. If improving existing ads: **read `action_items`** (section above) and act on them.
3. Load ad group keywords (`get_keywords` filtered to that `ad_group_id`).
4. Write H/D using **Keyword density** + **Semantic diversity** (both mandatory).
5. Preview (`confirm=false`) → user confirms → `confirm=true`.

---

## HARD RULE — semantic diversity (not synonym stacking)

**Root cause of many AVERAGE route RSAs:** 10–12 of 15 headlines are the *same message* with swapped synonyms:

`Transfer Gdańsk Poznań` / `Transport Gdańsk Poznań` / `Przewóz Gdańsk Poznań` / `Taxi Gdańsk Poznań` / `Kierowca Gdańsk Poznań`

Google treats that as **low meaning diversity** → Ad Strength stays Average even when strings are unique and keyword density looks fine.

**Excellent pattern** (e.g. Individual Trips, Airport EN): headlines span **different meaning categories** — brand/USP, features, geo/coverage, CTAs, trust — not 10× “vehicle word + cities”.

This is a **template bug** across ~24 route ad groups (Miasta, Kurorty, Lotnisko, International). Fix systemically with one shared pool, not ad-by-ad improvisation.

### Forbidden pattern

- Do **not** ship ≥4 headlines that only differ by service synonym  
  (`transfer` / `transport` / `przewóz` / `taxi` / `kierowca` / `przejazd` / `prywatny transfer`) + the same route/cities.
- Cap **route+synonym** headlines at **≤4** of 15 (prefer **3–4**).
- Cap any single *idea* (same claim after stripping synonyms) at **≤2** headlines.

### Required meaning categories (≥6 of these across 15 H)

| # | Category | Role | Examples (adapt language PL/EN) |
|---|----------|------|----------------------------------|
| 1 | Route / keyword match | Relevance | Primary KW / city–city phrase (≤4 H) |
| 2 | Brand / USP | Differentiator | Executive chauffeur, private transfer brand angle |
| 3 | Feature / product | Offer facts | Fixed price, 24/7, door-to-door, up to 8 pax, meet & greet |
| 4 | Price / guarantee | Risk reducer | No hidden fees, fixed fare, free cancellation (if true) |
| 5 | Trust / proof | Credibility | Experienced drivers, English-speaking, insured, reviews |
| 6 | CTA | Action | Book now, Reserve online, Request a quote, Instant quote |
| 7 | Geo / coverage | Context | Coast, lakes, cities, airport, Poland & Europe (when true) |
| 8 | Urgency / convenience | Motive | Same-day, online in 2 min, confirmation instantly |

Descriptions (4): each should emphasize a **different** mix (offer + proof + CTA), not three clones of “private transfer city–city”.

### Balanced headline pool (default for ALL route groups)

Use this split for Miasta / Kurorty / Lotnisko / International (and any city–city RSA):

| Slots | Type | Content |
|------:|------|---------|
| **4–5** | Route-specific | Primary KW / direction / city names / landing theme |
| **~10** | Universal pool | Shared across campaigns: CTA, features, trust, price/guarantee, USP — **reuse** the same strong set; only translate or lightly adapt. Ready lists: **`rsa-route-headline-pools`**. |

**Workflow when creating or bulk-fixing route RSAs:**

1. Maintain one **universal headline bank** (~10 approved lines per language).
2. Per ad group: write **4–5 route-specific** lines from keywords + landing.
3. Merge → 15 unique H; run density + diversity checks; then mutate.

Do **not** regenerate 15 near-identical “Transfer/Transport/…” lines per city.

### Priority when optimizing at scale

| Mode | Scope | When |
|------|--------|------|
| Conservative | Fix POOR / broken serving first; resolve PENDING duplicates | Small triage |
| **Balanced (default)** | Apply universal pool + 4–5 route H to **all** route groups | Systemic Average pattern |
| Full | Also sitelinks ≥8–9 + keyword density pass | When Google still tips assets |

---

## Slot counts (quantity)

| Asset | API max | Target for Good+ | Absolute minimum we ship |
|-------|---------|------------------|---------------------------|
| Headlines | 15 | **15** | **10** (prefer 12–15) |
| Descriptions | 4 | **4** | **3** (prefer 4) |

- ≤30 characters per headline (DKI counts **default** text inside `{KeyWord:…}`, not braces).
- ≤90 characters per description.
- **Unpin** almost everything (pin only legal/brand if required). Pins reduce combinations and hurt Ad Strength.

---

## Keyword density checklist (mandatory)

Ad Strength is driven by **asset–keyword relevance**. Follow these numbers every time — **together with** semantic diversity (density alone is not enough).

### A. Whole keyword in one field (Google rule)

- A keyword must appear **entirely inside a single headline** (or a single description).
- **Never** split one keyword across two headlines (e.g. H1=`transfer` + H2=`airport warsaw` for keyword `transfer airport warsaw`).
- If the keyword is **longer than 30 characters**, put the **full phrase in a description** (≤90), and use a shortened natural variant in headlines.

### B. Headlines — density targets

Pull ENABLED keywords for the ad group (sort by impressions/clicks when available). Then:

1. **Primary theme keyword** (main phrase of the ad group):  
   include the **full phrase** (or closest natural ≤30 form) in **≥4 headlines** (max **6**).  
   Those 4–6 must still be **different ideas** (not synonym swaps of the same line).

2. **Each other popular keyword** in the group (top by traffic, typically top 3–8):  
   at least **1 dedicated headline** containing that **full** keyword (or ≤30 natural form).

3. **Coverage floor:** at least **50% of headlines** (≥8 of 15, or ≥5 of 10) must contain **at least one** ad-group keyword (exact phrase or clear close variant / same stem in the ad language).

4. **Do not keyword-stuff:** do **not** put the same keyword in all headlines. Cap any single keyword at **6** headlines. Remaining headlines = brand, USP, proof, CTA, geo, urgency — **without** repeating the same idea.

5. **Optional DKI:** 1–2 headlines with `{KeyWord:Default ≤30}` to lift relevance; default text must be a real fallback, not empty.

### C. Descriptions — density targets

1. Ship **4** unique descriptions when possible.
2. At least **2 of 4** descriptions include the **primary keyword** (or long keyword that did not fit in a headline).
3. At least **1** description includes a **secondary popular keyword** from the ad group.
4. Remaining copy = offer, USP, trust, CTA — still unique, no clones.

### D. Sitelinks

Google Ad Strength counts sitelinks at account / campaign / ad group. Aim **≥6**, prefer **≥8–9** if tip stays “Add 3 more sitelinks…”.

If `action_items` contains **“Add … sitelinks”**:

1. `get_campaign_assets(campaign_id)` — count ENABLED `SITELINK`.
2. Add missing sitelinks with `add_sitelinks` (unique link_text ≤25, final_url, optional desc1/desc2 ≤35).
3. Do **not** treat this as an RSA text problem when H/D are already full (15/4) **and** diversity is OK.

**Cross-campaign identical sitelink labels** (same “FAQ / Kontakt / Flota” on Miasta + Kurorty + Lotnisko): **low impact on Ad Strength**, but hurts **relevance/CTR**. Keep the same destination URLs; vary `link_text` + descriptions per campaign theme — see **`sitelink-diversity`**.

---

## Quick recipe (copy when editing)

```
1. get_keywords(ad_group_id) → top ENABLED phrases
2. Draft 15 headlines with BALANCED POOL:
   - 4–5 route/KW-specific (different ideas, NOT Transfer/Transport/Taxi×N)
   - ~10 universal: USP, feature, price/guarantee, trust, CTA, geo/coverage
   - ≥6 meaning categories covered; ≤4 synonym+route lines
3. Draft 4 descriptions: ≥2 primary KW, ≥1 secondary; distinct angles
4. Density: primary KW in ≥4 H (≤6); ≥50% H with any KW; no pins
5. update_responsive_search_ad / create_* → confirm flow
6. PENDING Ad Strength for hours is normal; re-check get_ad_strength later
```

---

## Tools

- List strength: `get_ad_strength` / `get_creatives` → `ad_strength`, `action_items`.
- Full text before edit: `get_creatives(ad_group_id=…)` or `ad_id=…` or `text_contains=…`.
- Local checklist: `evaluate_rsa_for_ad_strength` (counts + density + synonym-stack warning).
- Mutate: `update_responsive_search_ad` (prefer fix existing `ad_id`).
- New empty group: `create_responsive_search_ad`.
- New group+RSA: `create_ad_group_with_rsa`.

Unfiltered creatives may return `headlines_sample` only — **not** an API failure; re-call with filter.

---

## Do not confuse

- Ad Strength ≠ Keyword Quality Score  
- Ad Strength ≠ policy approval / ENABLED serving  
- PENDING after create/edit is normal (Google recalculates)  
- Unique strings ≠ semantic diversity (synonym stacking still hurts)  
- Keyword density without category diversity → often stuck on Average  

---

## Cite

When advising or mutating RSA, cite **`rsa-ad-strength`**.
