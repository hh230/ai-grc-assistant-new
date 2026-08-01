# mission-web-spike (TEMPORARY)

A **throwaway** React spike for Execution Slice **S1 (Missions View)**. It exists only to prove the
vertical slice reaches a UI that talks to the `grc-api` REST contract — and nothing deeper.

**The permanent Web host is deliberately undecided** (deferred to the first full frontend slice,
S4/S5, per the "no decision before need" rule). Do not build product UI here.

## The one rule it demonstrates

The ViewModel never exceeds the API boundary: React knows **only** the API's `MissionListItem` /
`MissionListResponse` shape (`src/api/missions.ts`) — never the Mission aggregate, the projection, a
DB row, or an ORM model. The REST API is the frontend's single contract.

## Run it locally

```bash
# 1) API (dev-seeded) on :8099
cd v2/apps/grc-api && uv run uvicorn grc_api.dev:app --port 8099
# 2) this app on :5199 (Vite proxies /v1 → :8099, so same-origin, no CORS)
npm --prefix v2/apps/mission-web-spike install
npm --prefix v2/apps/mission-web-spike run dev
```

Then open http://localhost:5199. Credentials are seeded dev tenants (`dev-tenant-a`, `dev-tenant-b`).
