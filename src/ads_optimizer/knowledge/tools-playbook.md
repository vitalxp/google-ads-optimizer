---
id: tools-playbook
title: Playbook инструментов агента (lookup, RSA, мутации)
tags: tools, playbook, rsa, ad group, creatives, mutate, efficiency, api
priority: critical
updated: 2026-08-15
---

# Tools playbook

Цель: максимум пользы за минимум раундов. Сначала узкий lookup, потом mutate preview.

## Чтение (быстрые пути)

| Задача | Вызов |
|--------|--------|
| Обзор | `get_overview` / `get_campaigns` |
| Найти группу | `get_ad_groups(name_contains="Ustka")` |
| Список RSA + сила | `get_ad_strength` или `get_creatives` |
| **Полные** headlines/descriptions | `get_creatives(ad_group_id=...)` **или** `ad_id=...` **или** `text_contains="8 miejsc"` |
| Ключи | `get_keywords` |
| Минусы | `get_negative_keywords` |
| Assets | `get_campaign_assets` |
| Goals | `get_conversion_goals` |
| GA4 | `ga_overview`, `ga_channels`, … |

### Creatives / truncation

- Без фильтра список может быть сжатым (`headlines_sample`). Это **не** ошибка API.
- Нужны все активы → **сразу** `get_creatives` с `ad_group_id` / `ad_id` / `text_contains`.
- `ad_id` всегда есть в строках с объявлением. Не утверждать, что ID «не удалось получить».

### Пустые ad groups

- В `get_ads` / `get_creatives` / `get_ad_groups`: `empty_ad_group=true`, `status=NO_AD`.
- Есть `ad_group_id`, нет `ad_id` → создавать RSA через `create_responsive_search_ad`.

## Мутации (confirm flow)

Всегда: `confirm=false` → показать preview → «да» → `confirm=true`.

| Задача | Tool |
|--------|------|
| Кампания с нуля | `create_full_search_setup` |
| Только кампания | `create_search_campaign` |
| Пауза/вкл кампании | `set_campaign_status` |
| Бюджет | `update_campaign_budget` |
| Переименовать кампанию | `rename_campaign` |
| Ставки на существующей | `update_campaign_bidding` (maximize_clicks / conversions / tCPA / tROAS / manual_cpc) |
| Новая группа | `create_ad_group` |
| **Группа + RSA (+ключи)** | `create_ad_group_with_rsa` |
| **Переименовать группу** | `rename_ad_group(ad_group_id, name)` |
| RSA в **существующую** (в т.ч. пустую) | `create_responsive_search_ad` |
| Правка RSA | `update_responsive_search_ad(ad_id, headlines, descriptions, …)` |
| Пауза RSA | `set_ad_status` |
| Ключи | `add_keywords` / `set_keyword_status` |
| Минусы | `add_negative_keywords` |
| Sitelinks / callouts / snippets | `add_sitelinks` / `add_callouts` / `add_structured_snippet` |

## Типовые сценарии

### 1) «Нет объявления в группе X»

1. `get_ad_groups(name_contains=X)` → `ad_group_id`.
2. Если `empty_ad_group` → `create_responsive_search_ad` (не `create_ad_group_with_rsa`).
3. Preview → confirm.

### 2) «Исправь текст 8→7 мест»

1. `get_creatives(text_contains="8 miejsc")` или `ad_group_id=...` → полные H/D + `ad_id`.
2. Собрать новый набор (заменить 8→7 везде, сохранить сильные уникальные строки).
3. `update_responsive_search_ad` preview → confirm.

### 3) «Переименуй группу»

1. `get_ad_groups(name_contains=...)`.
2. `rename_ad_group` preview → confirm.

### 4) «Новая группа в текущей кампании»

1. `get_campaigns` → `campaign_id`.
2. `create_ad_group_with_rsa` (имя + URL + H/D + optional keywords).

## MCP vs AI Assistant

- **AI Assistant / gads-agent tools** — read + **write** (этот playbook).
- **Официальный google-ads-mcp** в Cursor — только чтение GAQL/customers. Мутации через него **не** делать и не обещать.

## Частые ошибки агента (не повторять)

- «Нет rename_ad_group» — есть.
- «Нет ad_group_id, группа новая» — смотреть `get_ad_groups`, пустые тоже с id.
- «API обрезал тексты RSA» — вызвать `get_creatives` с фильтром.
- «Bidding только при создании» — есть `update_campaign_bidding`.
- «Maximize Clicks нельзя» — можно (`target_spend.cpc_bid_ceiling_micros`).
