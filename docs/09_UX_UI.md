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
3. Бюджет?
4. Откуда?
5. Радиус?
6. Сколько людей?

Use defaults/presets; avoid giant technical form.

## AutoSignal builder
Language: `Позови меня, если...`
Fields: activity/category, days, time, budget, participant count, origin, radius.
One card = one AND rule. Do not build arbitrary boolean programming UI.

## Offer list
Up to 3 overlapping Offers. Each includes enough to choose: what/where/when, source-aware price, own distance, group state, CTA.

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

## Data status
Cached: `Данные обновлены 18 минут назад`.
Model: `Демонстрационные данные`.

## Errors
Always provide next action: retry/back/edit/use cached result.

## Accessibility
Focus, touch targets, contrast, semantic controls, no color-only meaning, reduced motion.

## MAX
Use official current MAX UI where helpful; verify mobile + web.
