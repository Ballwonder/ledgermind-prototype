
import os, requests

class PlaidBankConnector:
    def __init__(self):
        self.client_id=os.getenv("PLAID_CLIENT_ID")
        self.secret=os.getenv("PLAID_SECRET")
        self.env=os.getenv("PLAID_ENV","sandbox")
        self.base={
            "sandbox":"https://sandbox.plaid.com",
            "production":"https://production.plaid.com"
        }[self.env]

    @property
    def configured(self):
        return bool(self.client_id and self.secret)

    def _post(self,path,payload):
        if not self.configured:
            raise RuntimeError("Plaid credentials are not configured.")
        body={"client_id":self.client_id,"secret":self.secret,**payload}
        r=requests.post(self.base+path,json=body,timeout=30)
        r.raise_for_status()
        data=r.json()
        if data.get("error_code"):
            raise RuntimeError(data)
        return data

    def create_link_token(self,user_id="local-test-user"):
        return self._post("/link/token/create",{
            "user":{"client_user_id":user_id},
            "client_name":"LedgerMind Personal",
            "products":["transactions"],
            "country_codes":["CA"],
            "language":"en",
            "transactions":{"days_requested":180}
        })

    def exchange_public_token(self,public_token):
        return self._post("/item/public_token/exchange",{"public_token":public_token})

    def sync_transactions(self,access_token,cursor=None):
        added=[]; modified=[]; removed=[]; has_more=True
        while has_more:
            d=self._post("/transactions/sync",{
                "access_token":access_token,
                "cursor":cursor,
                "options":{"personal_finance_category_version":"v2"}
            })
            added += d.get("added",[])
            modified += d.get("modified",[])
            removed += d.get("removed",[])
            cursor=d.get("next_cursor")
            has_more=d.get("has_more",False)
        return {"added":added,"modified":modified,"removed":removed,"cursor":cursor}


def recurring_transactions(self,access_token):
    return self._post("/transactions/recurring/get",{
        "access_token":access_token,
        "options":{"personal_finance_category_version":"v2"}
    })
