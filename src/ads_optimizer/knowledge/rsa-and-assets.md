---
id: rsa-and-assets
title: RSA, расширения и креативы
tags: rsa, ads, headlines, descriptions, assets, extensions, rename
priority: high
updated: 2026-08-15
---

# RSA и assets

## Responsive Search Ad

- **Headlines:** 10–15 уникальных (цель **15**). ≤30 символов.
- **Descriptions:** 3–4 (цель **4**). ≤90 символов.
- **Keyword density (обязательно для Good/Excellent):** см. **`rsa-ad-strength`** —
  ≥50% headlines с ключом группы; primary KW в ≥4 H; целая фраза в одном поле;
  ≥2 descriptions с primary KW. Без stuffing (макс. 6 H на один ключ).
- **Semantic diversity (обязательно):** не штамповать 10× «Transfer/Transport/Taxi + города».
  ≥6 смысловых категорий; для маршрутов — **4–5 route-specific + ~10 universal** (CTA,
  фичи, доверие, цена/гарантия, УТП). См. **`rsa-ad-strength`**.
- **Pin:** только критичное. Лишний pin убивает комбинации и Ad Strength.

Перед любым create/update RSA: `get_knowledge("rsa-ad-strength")` + `get_keywords` по группе.

## Tools: создание / правка RSA

| Ситуация | Tool |
|----------|------|
| Пустая существующая группа (`NO_AD`) | `create_responsive_search_ad(ad_group_id, …)` |
| Новая группа + RSA в кампании | `create_ad_group_with_rsa` |
| Правка текстов существующего RSA | `update_responsive_search_ad(ad_id, …)` |
| Пауза/вкл объявления | `set_ad_status` |
| Полные тексты перед правкой | `get_creatives(ad_group_id\|ad_id\|text_contains)` |
| Переименовать группу | `rename_ad_group` после `get_ad_groups` |

ID групп: только `get_ad_groups(name_contains=...)`. Не выдумывать.

## Релевантность

- Часть заголовков = тема ad group / ключи.
- Final URL = страница оффера группы.
- DKI — осторожно (грамматика, бренд, конкуренты).

## Расширения (assets)

Приоритет: sitelinks, callouts, structured snippets, call (если телефония).

1. Список: `get_campaign_assets`.
2. `add_sitelinks` / `add_callouts` / `add_structured_snippet` (confirm).
3. Снять связь: `set_campaign_asset_status`.
Уровень: campaign. См. также `tools-playbook`.

## Оптимизация креативов

- Asset performance Best / Low за достаточный период.
- Low → заменить; не удалять всё сразу.
- Менять 30–40% слабых, сохраняя сильные.

## Запреты качества

- Кликбейт без соответствия лендингу; чужой бренд без оснований.
