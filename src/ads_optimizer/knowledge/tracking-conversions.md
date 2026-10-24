---
id: tracking-conversions
title: Конверсии и качество данных
tags: tracking, conversions, attribution, enhanced conversions, gtag, auto-tagging, value
priority: critical
updated: 2026-08-15
---

# Трекинг и конверсии

## База

- Primary conversion = бизнес-цель (lead submit, purchase, call >N сек).
- Вторичные (page_view, session_start, scroll) — **не** primary и лучше **вообще не** conversion events в GA4.
- Одно событие = одна запись; убрать дубли tag + import.
- Правильное значение value (для tROAS / value bidding).

## Диагностика Ads clicks >> GA4 paid sessions

1. `get_customer_tracking` — `auto_tagging_enabled` должен быть true.
2. Если false → `set_customer_auto_tagging(enabled=true)` (confirm).
3. Проверить лендинг: редиректы не срезают `gclid`; GA4 тег на всех страницах.
4. Часть «кликов» Ads может быть Local actions (calls/directions) — они в all_conversions / GOOGLE_HOSTED, не в website sessions.

## Мусорные conversion events / fake value

Симптомы: сотни GA4 «conversions» на десятки сессий; value-based bidding с дикими PLN.

Порядок:

1. `ga_list_conversion_events` — убрать page_view, session_start, scroll, user_engagement и т.п. через `ga_delete_conversion_event`.
2. Оставить purchase / booking_submit / lead.
3. `get_conversion_goals` → шумные импорты: `set_conversion_action_primary(false)` или `set_conversion_action_status=HIDDEN`.
4. Сломанный value (booking_route_calculated / stub value=1): `set_conversion_action_value` (`always_use_default_value`, `default_value`, currency).

Пока трекинг кривой — **не** паузить ключи по «нулевому CPA».

## Tools

- Ads goals: `get_conversion_goals`, `set_conversion_action_primary`, `set_conversion_action_status`, `set_conversion_action_value`.
- Tracking: `get_customer_tracking`, `set_customer_auto_tagging`.
- GA4: см. `google-analytics`.
- Campaign goals: `conversion-goals`.
