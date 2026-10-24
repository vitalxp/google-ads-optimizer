---
id: structure-and-segmentation
title: Структура аккаунта и сегментация
tags: structure, segmentation, brand, pmax, shopping, architecture
priority: critical
updated: 2026-08
---

# Структура и сегментация

## Кампании по каналу и интенту

| Слой | Зачем отдельно |
|------|----------------|
| Search Brand | Защита бренда, свой CPA/ROAS, контроль запросов |
| Search Non-brand | Основной performance Search |
| Search Competitor | Отдельный бюджет и креативы (юридически осторожно) |
| Shopping / PMax | Не смешивать бюджет и learning с классическим Search |
| Remarketing / Demand Gen | Другая воронка и креативы |

Смешение Brand + Non-brand в одной кампании размывает ставки и обучение.

## Ad groups

- **Тема = интент**, не «все услуги компании».
- 1 группа ≈ один оффер / один кластер запросов / одна посадочная (или очень близкие URL).
- Слишком узко (1 ключ = 1 группа) — ок для high-value Exact; избыточно для всего аккаунта.
- Lookup / rename / RSA в пустую группу: `get_ad_groups`, `rename_ad_group`, `create_responsive_search_ad` / `create_ad_group_with_rsa` — см. `tools-playbook`.

## Бюджеты и приоритет

1. Сначала закрыть Brand (не отдавать конкурентам дешёвые бренд-клики).
2. Non-brand money terms.
3. Эксперименты (новые темы, Broad) — отдельный небольшой бюджет.

## Каннибализация

- Одинаковые ключи в двух Search-кампаниях → непредсказуемый auction.
- PMax часто забирает бренд и высокие конверсии: мониторить brand queries / asset groups; при необходимости brand exclusions / отдельные Search Brand.

## Правило агента

Перед созданием новой кампании спросить/проверить: есть ли уже Brand/Non-brand слой; не плодить дубликаты тем.
