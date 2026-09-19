# 09 — UX/UI baseline

The Mini App is a compact utility inside MAX. It should answer, in order: what is happening now, whether the user needs to decide anything, and how to signal availability. It is not a landing page, dashboard, or collection of promotional cards.

## Visual system

- Use page, section, row, divider, and list-item structure by default.
- Reserve bordered cards for Offers and important current Plans.
- Keep page titles compact; do not repeat kicker/title/subtitle stacks.
- Use small, medium, and modal radii deliberately. Pills are for compact selectable tags, not every control.
- Use the lightning mark for the product identity and the strongest confirmed state only.
- Use one local SVG icon language for the four main destinations. Emoji are not interface icons.
- Keep gradients and shadows exceptional. Every token must work in light and dark mode.
- Desktop remains a centered, readable Mini App rather than becoming a sidebar dashboard.

## Navigation

The four destinations are `Главная`, `Авто`, `Планы`, and `Компания`. The top bar is compact. Bottom navigation is safe-area aware, uses 44 px touch targets, and indicates the active destination without a large selected tile.

## Home

Home is ordered by urgency:

1. the user's current Signal;
2. Plans the user has already responded to;
3. pending Invitations.

An active Signal is one compact summary containing its time, categories, Companies, meaningful optional constraints, and a quiet edit action. Cancellation is available but visually secondary. With no Signal, show one clear `Подать сигнал` action without a promotional empty-state card.

Confirmed, conditional, collecting, and waitlisted Plans retain distinct wording but share one restrained layout. `ДВИЖ СОБРАЛСЯ` is a strong status label, not a full-screen celebration.

The complete cross-company Offer pool remains visible and is grouped by the device's local day: `Сегодня`, `Завтра`, `Позже`. Home calls this section `Приглашения`. Signal creation stays reachable when invitations exist.

## Signal

Signal creation stays on one fast screen:

1. `Когда` presets;
2. `Что ок` multi-select categories;
3. `С кем` Company rows;
4. collapsed `Условия`;
5. the primary submit action.

Categories may use restrained multi-select chips. Companies use selectable rows so activity and audience are not visually confused. Budget, distance, and group size are secondary. `Ровно N` reveals a numeric field from 2 through 12. Distance appears only when a real saved place exists in the selected Companies' city. Mixed-city Company selection blocks submission.

Editing restores the current multi-category, multi-company, location, and exact-size values. Cancelling opens an accessible in-app confirmation dialog.

## Offers and progress

Offer is a real decision card. Its hierarchy is title, time, place, important price/distance facts, quiet Company context, group progress, applicable caveat, actions, and provider provenance.

The primary action is `Я в деле`, `Всё равно впишусь`, or `Встать в лист ожидания` according to backend fields. `Пас` is secondary. A full non-exact plan states that there are no places without offering a waitlist.

All collection states use the same compact dot-and-text progress language. It supports 2–12 people and only renders actual backend counts. A conditional responder sees their own private minimum and current response count; other users never do.

Near is an explicit, non-alarming exception such as `На 100 ₽ выше твоего лимита`. It always requires a deliberate action and never exposes the user's budget to anyone else.

A FROM price keeps `от` in the visible price and adds `Цена может быть выше`. A Place with unverified hours says `Режим работы лучше проверить`. Provider provenance and source links remain accessible but secondary.

## AutoSignals

AutoSignals are a settings list, not marketing cards. Each row contains name, schedule, categories, Company, concise constraints, switch, and an edit affordance. Delete stays inside edit/detail.

The editor groups name, Company, activity, schedule, and conditions with spacing and dividers. It preserves overnight schedules, saved-location rules, and generic exact N behavior.

## Plans

Plans are a single scannable upcoming list. Small status labels distinguish `Собираем`, `Ждём ещё людей`, `Лист ожидания`, and `ДВИЖ СОБРАЛСЯ`. Confirmed Plans can be visually stronger but use the same product-native structure.

Participant names appear only in confirmed states and only as provided by the backend privacy contract. Confirmed-open Plans state that another person may still join.

## Company and saved places

Company is a settings screen: current Company summary, Company switcher when needed, invitation action, saved places, city settings, and development tools only in development mode.

Companies and saved places use rows. A saved place exposes rename/default/delete through an accessible explicit action menu rather than several persistent buttons. No action relies on hover. City change uses a dialog that explains cancellation/pause consequences and reports affected counts after success.

## Empty, loading, and error states

Empty states use short state-specific copy rather than a repeated lightning-card composition. Keep `no Signal`, `no source results`, `no feasible plan`, `provider unavailable`, `no AutoSignals`, `no Plans`, and `no saved places` semantically distinct.

Loading is a small native indicator. Errors are concise, human, and include recovery where possible. Never expose internal state names or backend vocabulary.

## Accessibility and MAX

Maintain semantic headings, labels, `aria-pressed`, switch names, dialog semantics, visible focus, keyboard navigation, 44 px touch targets, non-color state cues, contrast, and reduced motion. Use MAX UI primitives where they clarify standard controls, and semantic HTML where a row or list is simpler.

Confirmation dialogs keep keyboard focus inside, preserve the focused field on
rerender, and restore the opener on close. Saved Signal conditions open during
editing even for a zero budget. Validation failures use readable messages rather
than raw API validation objects. The collecting status has separate light and
dark theme colors.

Production and MAX mode never mount development tools. The interface must be verified at 375 × 812, 430 × 932, and 1280 × 800 in light and dark themes where available, including long Russian copy and all product states.
