# Frontend AGENTS.md

Read root `AGENTS.md` first, then `docs/01_PRODUCT.md`, `docs/04_USER_FLOWS.md`, `docs/09_UX_UI.md`, `docs/10_ACCEPTANCE_CRITERIA.md`, `docs/12_SECURITY_PRIVACY.md`.

## Stack
- React
- TypeScript
- Vite
- official current MAX UI where suitable
- typed client to our backend

## Rules
- Mobile-first; MUST also work in MAX web.
- Consumer Mini App, not admin dashboard.
- Never implement privacy-sensitive matching in client.
- Never call leisure providers directly from browser.
- Show up to 3 overlapping Offers; never auto-select.
- Near has a distinct explicit confirmation UI.
- Show only the current user's own distance/origin-derived data.
- Never label straight-line km as travel time.
- Do not add a second vote after Offer selection.
- All async screens need loading/success/empty/error/expired states.
- Use Russian UI copy unless product language changes explicitly.
