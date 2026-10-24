---
id: google-analytics
title: Google Analytics 4 — статистика и связь с Ads
tags: analytics, ga4, events, conversion events, ads link, landing, cleanup
priority: high
updated: 2026-08-15
---

# Google Analytics 4

OAuth тот же, что для Ads (`.env` / Setup → Sign in with Google). Нужны скоупы Analytics + `GA4_PROPERTY_ID` в `.env`.
Если ошибка scopes: Setup с галочкой Analytics или `gads-agent init --with-analytics`.
В GCP проекте включить Analytics Data API и Analytics Admin API.

## Статистика

- `ga_status` / `ga_list_properties` — подключение и property.
- `ga_overview` / `ga_channels` / `ga_landing_pages` / `ga_events`.

Сверяйте Paid Search с Ads clicks. Bounce 0 + conversions >> sessions → обычно мусорные conversion events, не «идеальный сайт».

## Управление conversion events

- Список: `ga_list_conversion_events`.
- Добавить: `ga_create_conversion_event` (confirm).
- **Снять метку conversion:** `ga_delete_conversion_event` (event_name или resource_name, confirm).
- Держать только бизнес-события (purchase, booking_submit, generate_lead…).
- Не помечать page_view / session_start / scroll / form_start как conversions.

После чистки GA4 — в Ads demote/hide импорты (`set_conversion_action_primary` / `HIDDEN`). См. `tracking-conversions`.

## Связь с Ads

- `ga_list_google_ads_links` / `ga_create_google_ads_link`.
- Auto-tagging: `get_customer_tracking` / `set_customer_auto_tagging`.

## Порядок для агента при «сломанном трекинге»

1. `ga_status` + `ga_list_conversion_events` + `get_conversion_goals` + `get_customer_tracking`.
2. Предложить cleanup preview (delete noise events + demote Ads actions + fix values).
3. Confirm → apply.
4. Только потом оптимизация ключей/ставок.
