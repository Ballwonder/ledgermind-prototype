# Run LedgerMind Working Prototype

From the extracted project directory:

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

`http://127.0.0.1:8000/prototype`

Fastest safe test:
1. Open `/prototype`.
2. Import a CSV with columns `date,description,amount`.
3. Upload a text receipt/invoice if desired.
4. Click **Process Everything**.
5. Inspect individual transactions with **Analyze**.

Sign convention:
- money in = positive
- money out = negative

Plaid/Gmail/Outlook remain disabled until server-side OAuth credentials are configured.
