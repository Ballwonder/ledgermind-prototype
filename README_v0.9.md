# LedgerMind Personal v0.9 — End-to-End Sandbox

This version consolidates the browser dashboard and persistent FastAPI/SQLAlchemy backend into one runnable sandbox.

## Run
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- `http://127.0.0.1:8000/personal`

Core sandbox endpoints:
- `POST /api/v09/reset`
- `GET /api/v09/state`
- `POST /api/v09/demo-cycle`
- `GET /api/v07/dashboard`
- `GET /api/v07/transactions`
- `POST /api/v07/transactions/{id}/category`
- `GET /api/v07/wealth`
- `POST /api/v08/evidence`
- `POST /api/v08/evidence/match`
- `POST /api/v08/insights/anomalies`

The end-to-end test resets a temporary database, verifies 12 seeded transactions, adds and matches receipt evidence, runs anomaly detection, corrects Amazon's category, and verifies both the correction record and learned merchant memory.

## Security status
Synthetic/Plaid Sandbox data only. This is not approved for real banking or mailbox data yet.
