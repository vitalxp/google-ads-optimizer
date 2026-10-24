---
id: bidding-strategies
title: Стратегии ставок и ramp-up
tags: bidding, tcpa, troas, smart bidding, maximize conversions, cpc
priority: critical
updated: 2026-08-15
---

# Стратегии ставок

## Выбор по зрелости

| Ситуация | Стратегия |
|----------|-----------|
| Нет/мало конверсий (<15–30 / мес на кампанию) | Maximize Clicks (с потолком CPC) или Manual CPC |
| Есть стабильные конверсии, цель — объём | Maximize Conversions |
| Есть стабильный CPA | Target CPA (tCPA) |
| Ценность конверсий различается | Maximize Conversion Value / tROAS |
| Нужен трафик на тест лендинга | Maximize Clicks на короткое окно |

Пороги ориентировочные: Smart Bidding устойчивее при **≥30 конверсиях / 30 дней** на кампанию (чем больше — тем лучше). Ниже — осторожный ramp.

## Ramp-up

1. Собрать данные (клики/конверсии) на мягкой стратегии.
2. Переход на Maximize Conversions **без** target → 1–2 недели.
3. Выставить tCPA ≈ **исторический CPA × 1.0–1.2** (не занижать «для экономии»).
4. Менять tCPA не чаще чем раз в несколько дней и **не больше ~15–20%** за раз.
5. В период обучения не менять одновременно: бюджет, креативы, ключи, гео, цель.

## Чего не делать

- tCPA сильно ниже факта → кампания «задыхается», 0 показов.
- Скачки бюджета >30–50% в день обучения.
- Частые переключения стратегий туда-сюда.
- Оптимизация под микроконверсии как primary, если цель — продажи/лиды.

## Maximize Clicks в агенте

`update_campaign_bidding` с `maximize_clicks` работает (в API это TargetSpend).
Update mask обязан быть листовым: `target_spend.cpc_bid_ceiling_micros`
(не `target_spend` — иначе FIELD_HAS_SUBFIELDS). Потолок CPC опционален.
То же правило для других стратегий: mask на подполе (`maximize_conversions.target_cpa_micros` и т.д.).

## Смена стратегии на существующей кампании

Использовать `update_campaign_bidding` (preview → confirm), не создавать кампанию заново:
- `maximize_clicks` (+ optional `cpc_bid_ceiling`)
- `maximize_conversions` (+ optional `target_cpa`)
- `target_cpa` (обязателен `target_cpa`)
- `maximize_conversion_value` / `target_roas`
- `manual_cpc`

Текущий тип смотреть в `get_campaigns` → `bidding_strategy_type`.
Карта tools: `tools-playbook`.

