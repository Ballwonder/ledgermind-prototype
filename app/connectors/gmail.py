
import os, base64
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

READONLY_SCOPE="https://www.googleapis.com/auth/gmail.readonly"

class GmailEvidenceConnector:
    def __init__(self, token_data: dict):
        self.credentials=Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=[READONLY_SCOPE],
        )

    def service(self):
        return build("gmail","v1",credentials=self.credentials,cache_discovery=False)

    def search_receipts(self, query='newer_than:90d (receipt OR invoice OR "order total")', max_results=50):
        svc=self.service()
        listing=svc.users().messages().list(userId="me",q=query,maxResults=max_results).execute()
        out=[]
        for item in listing.get("messages",[]):
            msg=svc.users().messages().get(userId="me",id=item["id"],format="metadata",
                metadataHeaders=["From","Subject","Date"]).execute()
            headers={h["name"].lower():h["value"] for h in msg.get("payload",{}).get("headers",[])}
            out.append({
                "message_id":item["id"],
                "thread_id":msg.get("threadId"),
                "from":headers.get("from"),
                "subject":headers.get("subject"),
                "date":headers.get("date"),
                "snippet":msg.get("snippet","")
            })
        return out
