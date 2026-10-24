---
id: search-campaign-launch
title: Запуск Search-кампании с нуля
tags: setup, launch, search, campaign, onboarding
priority: critical
updated: 2026-08-15
---

# Запуск Search с нуля

## Порядок (не пропускать)

1. **Конверсии** — хотя бы одно primary conversion action, корректное окно атрибуции, без дублей. Без этого Smart Bidding бесполезен.
2. **Гео и язык** — Location option = **Presence** (люди в локации / регулярно там), не «interested in». Исключить страны/регионы вне оффера.
3. **Сеть** — Search only; Search Partners включать только осознанно (часто трафик хуже).
4. **Структура** — отдельные кампании: Brand / Non-brand / Competitor (если нужно). Не смешивать в одной кампании.
5. **Ad groups** — узкие темы (1 intent-кластер ≈ 5–20 ключей), не «одна группа на всё».
6. **Ключи** — старт: Exact + Phrase на money terms; Broad — только при Smart Bidding + сильных конверсиях + активных минусах.
7. **Минус-листы** — shared negatives с дня 1: free, job, diy, pdf, login, irrelevant geo/intent.
8. **RSA** — 8–15 headlines, 3–4 descriptions; пин sparingly (макс. 1–2 критичных).
9. **Бюджет** — дневной бюджет ≥ 10–15× целевой CPA (или достаточно для обучения). Кампания **PAUSED** до проверки превью → Enable после чеклиста.
10. **Ставки** — при малом объёме: Maximize Clicks / Manual CPC → после стабильных конверсий tCPA/Maximize Conversions. Не ставить жёсткий tCPA ниже исторического CPA в день 1.

## Tools агента при запуске

- С нуля: `create_full_search_setup` (кампания + группа + ключи + RSA), по умолчанию PAUSED.
- Новая группа в существующей кампании: `create_ad_group_with_rsa`.
- Пустая группа без RSA: `get_ad_groups` → `create_responsive_search_ad`.
- Карта вызовов: статья `tools-playbook`.

## Чеклист перед Enable

- [ ] Landing URL совпадает с интентом ключей
- [ ] Final URL доступен, мобильный, быстрый
- [ ] Нет пересечения Brand и Non-brand без правил приоритета
- [ ] Минус-слова на уровне кампании/shared list
- [ ] Бюджет и лимиты согласованы с владельцем аккаунта

## Типичные ошибки

- Сразу Broad + Maximize Conversions без истории → слив бюджета.
- Location «Presence or interest» → лишний гео-трафик.
- Одна mega ad group → низкая релевантность RSA.
- Создание ENABLED без подтверждения пользователя (агент: всегда PAUSED по умолчанию).
