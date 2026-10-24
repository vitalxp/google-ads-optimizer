---
id: rsa-route-headline-pools
title: Route RSA universal headline pools (PL / EN)
tags: rsa, headlines, routes, ad strength
priority: high
updated: 2026-10-23
---

# Route RSA — universal headline pools

Use with **`rsa-ad-strength`** (balanced pool: **4–5 route-specific + ~10–12 universal**).

These lists are generic examples for intercity / airport transfer Search campaigns.
Do **not** stack Transfer/Transport/Taxi × N synonyms per city.

## Structure per RSA (15 H)

| Slots | Role |
|------:|------|
| **H1–H3** | Route-specific (primary KW / cities / direction) — unique per ad group |
| **H4–H15** | Universal pool below (same across groups in that language) |

Plus **4 descriptions**: 1 route-led + 3 universal angles (comfort, booking, door-to-door / invoice).

## PL universal pool (H4–H15)

1. Stała Cena – Bez Dopłat  
2. Przejrzysta Cena z Góry  
3. Brak Ukrytych Opłat  
4. Doświadczony Kierowca  
5. Punktualny Kierowca  
6. Profesjonalna Obsługa  
7. Komfortowe Auto, Klimatyzacja  
8. Duży Bagażnik na Walizki  
9. Fotelik Dziecięcy na Życzenie  
10. Rezerwacja Online 24/7  
11. Potwierdzenie od Ręki  
12. Odbiór Door-to-Door  

## EN universal pool (H4–H15)

1. Fixed Price, No Hidden Fees  
2. Transparent Pricing Upfront  
3. No Extra Charges Ever  
4. Experienced Driver  
5. Punctual Door-to-Door  
6. Air-Conditioned Car  
7. Spacious Luggage Space  
8. Child Seats On Request  
9. Book Online 24/7  
10. Instant Confirmation  
11. VAT Invoice Available  
12. Book Your Transfer Now  

## Route-specific examples (H1–H3)

**PL:** `Transfer Gdańsk–Poznań` · `Prywatny Transfer Poznań` · `Z Gdańska do Poznania`  
**EN:** `Gdańsk to Berlin Transfer` · `Private Transfer to Berlin` · `Gdańsk–Berlin Private Ride`  

Adapt cities; keep ≤30 chars; put the whole keyword in one field.

## When creating / fixing route RSAs

1. Copy the universal pool for the language.  
2. Write 3–5 route lines from `get_keywords` + the landing page.  
3. Merge to 15 H + 4 D → `evaluate_rsa_for_ad_strength` → `update_responsive_search_ad`.  
4. Cite **`rsa-route-headline-pools`** + **`rsa-ad-strength`**.

## Constraints that often fail mutates

- Do **not** use Unicode arrows (`→`) in headlines — use an en-dash `–` or a hyphen. Google may reject the mutate.
- Final URL must return **HTTP 200**. Broken landings become `DESTINATION_NOT_WORKING` and block RSA updates.
- Check landings against **your** sitemap (or `POST /api/urls/check`) before apply.
