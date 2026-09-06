# LedgerMind Personal v0.7

v0.7 consolidates the visual prototype and integration prototype around a persistent backend data model.

Run:
1. Create and activate a Python virtual environment.
2. `pip install -r requirements.txt`
3. `uvicorn app.main:app --reload`
4. Open `http://127.0.0.1:8000/personal`

New API:
- GET `/api/v07/dashboard`
- GET `/api/v07/transactions`
- POST `/api/v07/transactions/{id}/category`
- GET `/api/v07/wealth`

The frontend automatically uses the v0.7 backend when served by FastAPI. If opened as a standalone HTML file it falls back to its built-in sample dataset.

Security status:
Use synthetic/Plaid Sandbox data only. Real personal financial/email data should wait for production authentication, CSRF protection, verified webhooks, OAuth state/PKCE, HTTPS, managed encrypted storage, data deletion controls and secret management.
