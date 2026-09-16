# 09 — UX/UI baseline

This defines interaction, not final visual design. Figma/screenshots override visual styling once added.

## Navigation
Keep MVP small: Home, AutoSignals, Plans, Profile/Locations. Avoid admin-dashboard feel.

## Home
Primary CTA: `⚡ Подать сигнал`.
Also show active Signal, AutoSignals and relevant Offer/ConfirmedPlan.

## Signal form
Progressive sections:
1. Когда?
2. Что интересно?
3. Бюджет? (необязательно)
4. Откуда?
5. Радиус? (необязательно; при выборе точки)
6. Сколько людей?

Use defaults/presets; avoid giant technical form.

## AutoSignal builder
Language: `Позови меня, если...`
Fields: activity/category, days, time, budget, participant count, origin, radius.
One card = one AND rule. Do not build arbitrary boolean programming UI.

## Offer list
Show the complete current Offer pool from all user's companies. Each card identifies its company and includes enough to choose: what/where/when, available source-aware price, own distance, group state and CTA. Sort only for navigation; do not hide lower-ranked offers.

## Exact Offer
```text
🎮 ПК-клуб
Сегодня 20:00–23:00
~400 ₽
3.2 км от твоей точки
Собирается 4 человека
[ Я в деле ] [ Пас ]
```

## Near Offer
```text
🎮 ПК-клуб
Цена: 400 ₽
Твой лимит: 300 ₽
На 100 ₽ выше
[ Всё равно пойду ] [ Пропустить ]
```
No prechecked acceptance.

## Confirmed
Strong success: `⚡ ДВИЖ СОБРАЛСЯ`.
Show what/where/when, price/source caveat, user's distance, confirmed participants according to reveal policy, share/open in MAX.

## Empty state
Never only “Ничего нет”. Explain lack of exact plan and offer a private Near/edit action if available.

## Optional metadata
When provider data is absent, omit its row entirely: do not show “Цена неизвестна”, “Цена не указана” or placeholder venue/image/description. This presentation rule never weakens matching hard constraints.

If the user set a budget/radius but the provider lacks price/coordinates, the backend treats the item as Unverified and does not send an Offer. The UI must not claim that it was a rejection or a compatible option.

## Data status
Cached: `Данные обновлены 18 минут назад`.
Model: `Демонстрационные данные`.

## Errors
Always provide next action: retry/back/edit/use cached result.

## Accessibility
Focus, touch targets, contrast, semantic controls, no color-only meaning, reduced motion.

## MAX
Use official current MAX UI where helpful; verify mobile + web.
