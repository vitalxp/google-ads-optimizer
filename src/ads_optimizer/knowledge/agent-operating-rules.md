---
id: agent-operating-rules
title: Правила работы агента с базой знаний
tags: agent, tools, workflow, confirmation, knowledge, playbook
priority: critical
updated: 2026-08-16
---

# Правила агента

## Источники истины

| Вопрос | Источник |
|--------|----------|
| Как настраивать / оптимизировать / вести | **База знаний** (`search_knowledge` → `get_knowledge`) |
| Карта tools / сценарии | Статья **`tools-playbook`** (читать первой при работе с API) |
| Метрики, ID, статусы, списки | **Google Ads tools** этого приложения |
| Полные тексты RSA / правка креативов | `get_creatives` с фильтром + `update_responsive_search_ad` |
| Правила RSA Good/Excellent + плотность ключей + смысловое разнообразие | **`rsa-ad-strength`** (обязательно до create/update RSA) |
| Google tips на объявлении (`action_items`) | **Всегда читать** из `get_ad_strength` / `get_creatives`; sitelinks → `add_sitelinks` |
| Цели / conversion actions | `get_conversion_goals` + mutate (`conversion-goals`) |
| Сессии / события / лендинги | **GA4** (`ga_*`, `google-analytics`) |
| Идеи ключей / объёмы | **DataForSEO** → fallback Keyword Planner |
| Read-only GAQL в Cursor IDE | Официальный `google-ads-mcp` (**не** для мутаций) |
| Чеклист запуска | `get_setup_checklist` + KB |

## Обязательный порядок

1. Методика → `search_knowledge` (часто `tools-playbook` + тематическая статья).
2. Любой create/update RSA → сначала **`rsa-ad-strength`** + ключи группы (`get_keywords`).
3. Факты аккаунта → overview / campaigns / `get_ad_groups` / keywords / ads / creatives.
4. Рекомендации = KB + факты (без выдуманных метрик).
5. Мутации → preview (`confirm=false`) → явное «да» → `confirm=true`.
6. Новые кампании по умолчанию **PAUSED**.
7. ID только из tools — никогда не выдумывать `ad_group_id` / `ad_id` / `criterion_id`.

## Lookup ID

| Нужно | Инструмент |
|-------|------------|
| `ad_group_id` по имени | `get_ad_groups(name_contains=...)` |
| Пустые группы | `empty_ad_group=true` / `status=NO_AD` + `ad_group_id` |
| Полные H/D + `ad_id` | `get_creatives(ad_group_id|ad_id|text_contains=...)` |
| Ключ для паузы | `get_keywords` → `ad_group_id` + `criterion_id` |

## Нельзя говорить «API недоступно», если tool есть

В т.ч.: `rename_ad_group`, RSA в пустую группу, `create_ad_group_with_rsa`, пауза ключей/объявлений,
`update_campaign_bidding`, sitelinks, минусы, goals, GA4, полные тексты RSA
(фильтр `get_creatives`, не «обрезка API»).

## Запрещено

- Best practices в обход KB; веб-поиск вместо KB.
- Mutate без подтверждения; обещания эффекта без данных.
- Путать официальный MCP (read-only) с mutate-tools AI Assistant UI.

## Формат ответа

Кратко: KB (cite id) → факты/ID → превью → следующий шаг.
