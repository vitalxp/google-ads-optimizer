---
id: keywords-match-negatives
title: Ключи, типы соответствия, минус-слова
tags: keywords, match types, negatives, broad, exact, phrase
priority: critical
updated: 2026-08
---

# Ключи и минус-слова

## Типы соответствия (практика 2025–2026)

- **Exact** — контроль money/brand terms, предсказуемый CPA.
- **Phrase** — расширение с сохранением порядка смысла; основной «рабочий» тип на старте.
- **Broad** — охват и discovery **только** при: Smart Bidding, качественных конверсиях, регулярном разборе search terms, готовых минусах. Иначе — основной источник слива.

Не дублировать один и тот же ключ во всех трёх типах без причины (шум в отчётах и ставках).

## Исследование ключей

1. Сиды → DataForSEO / Keyword Planner.
2. Отбор по: volume, competition, релевантность офферу, коммерческий интент.
3. Кластеризация по ad group до загрузки.
4. Минус-кандидаты собирать параллельно (информационные, бесплатные, вакансии).

## Минус-слова

**Shared lists (обязательный минимум):**
- free / darmow / gratis / скачать / pdf / torrent
- job / praca / vacanc / salary / wynagrodzenie
- diy / how to / tutorial (если не инфо-продукт)
- login / personal account (если не SaaS login-intent)
- geo вне зоны доставки/услуги

**Уровни:** shared list → campaign → ad group (точечно).

**Brand:** в non-brand кампаниях часто минусуют свой бренд (и наоборот), чтобы слои не пересекались.

## Search terms → ключи

- Конвертящий релевантный term → добавить Exact/Phrase в нужную группу.
- Мусор → negative Exact/Phrase через `add_negative_keywords` (campaign или ad group) с confirm.
- Не раздувать группу до 100+ ключей без кластеризации.

## Инструменты агента

- Список: `get_negative_keywords`
- Добавление: `add_negative_keywords` (не GAQL; GAQL только SELECT)
- По умолчанию match EXACT для точечного search term; PHRASE для семейства запросов

