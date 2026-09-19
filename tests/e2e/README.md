# E2E tests

There is no committed browser E2E runner yet. `frontend/src/app/App.test.tsx`
checks UI flows with a mocked API; it is not an end-to-end browser test.
`backend/tests/test_postgres_reliability.py` checks transactions and concurrency
against a dedicated PostgreSQL test database.

For manual browser verification, start `docker compose up --build`, open
`http://localhost:8080`, and follow the walkthrough in the root README and
`docs/11_TEST_PLAN.md`. Use separate, explicitly named demo users and a demo
Company. Cover Signal creation/edit/cancel, Exact and budget Near invitations,
two-person confirmation, AutoSignal editing, empty/error states and keyboard
dialog navigation. Verify 375 × 812, 430 × 932 and 1280 × 800 viewports.

The `/development/seed-demo/{group_id}` endpoint can create explicitly marked
model invitations after compatible Signals exist. It is development-only and
does not verify KudaGo or real MAX delivery. Real MAX mobile/web verification
still requires the registered bot and deployment described in the root README.
