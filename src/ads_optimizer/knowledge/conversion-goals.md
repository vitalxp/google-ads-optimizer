---
id: conversion-goals
title: Цели кампании Primary/Secondary и custom goals
tags: goals, conversions, primary, campaign goals, custom conversion goal, bidding
priority: critical
updated: 2026-08
---

# Управление целями в кампании

## Что менять

- **Primary** (`primary_for_goal=true`) — входит в Conversions и в Smart Bidding.
- **Secondary** (`primary_for_goal=false`) — только All conversions, ставки не оптимизирует (если не в custom goal).
- Статус conversion action: `ENABLED` | `HIDDEN` | `REMOVED` (не PAUSED).
- `include_in_conversions_metric` через API не меняется — используйте Primary/Secondary.

## Уровни

1. Аккаунт: `customer_conversion_goal` (category + origin, флаг `biddable`).
2. Кампания: `goal_config_level=CAMPAIGN` + `campaign_conversion_goal`.
3. Custom goal: подмножество conversion actions, затем attach к кампании.

По умолчанию кампания наследует цели аккаунта (`CUSTOMER`). Не переключайте на CAMPAIGN без нужды.

## Tools

1. Сначала `get_conversion_goals` (опционально `campaign_id`).
2. Primary/Secondary: `set_conversion_action_primary`.
3. Скрыть действие: `set_conversion_action_status` status=HIDDEN.
4. Biddable category/origin аккаунта: `set_customer_conversion_goal`.
5. То же на кампании: `set_campaign_conversion_goal` (это ставит CAMPAIGN level).
6. Custom subset: `create_custom_conversion_goal` + optional `campaign_id`.
7. Вернуть аккаунтные цели: `set_campaign_goal_config` goal_config_level=CUSTOMER.

Все mutate — preview (`confirm=false`), затем явное «да», затем `confirm=true`.

## Правила

- Одна бизнес-цель Primary (лид / покупка). Микроконверсии — Secondary.
- Не менять primary goals в середине обучения tCPA/tROAS без причины.
- После смены целей подождать накопления данных, не крутить ставки сразу.
---
