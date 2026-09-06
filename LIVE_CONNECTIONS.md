# LedgerMind Personal — Live Connection Setup

## Bank connection
The code includes a real Plaid adapter. It defaults to Sandbox. Add your own Plaid developer credentials to `.env` before enabling a real connection.

The application must never ask you to paste your online-banking username or password into LedgerMind. Bank authentication belongs inside the provider's Link/institution flow.

Production mode is deliberately not enabled automatically. Move from Sandbox to Production only after the provider has approved the application and the app has secure token storage.

## Gmail
Production Gmail access requires a Google Cloud OAuth client and user consent. Use the narrowest useful permission; for receipt discovery, read-only is preferable to mail modification.

A production implementation should:
1. OAuth-authorize the mailbox.
2. Search only for likely financial evidence.
3. Fetch matching message metadata/body/attachments.
4. Store only evidence needed for the financial record.
5. Encrypt refresh tokens and allow revocation/deletion.

## Privacy boundary
Personal financial and email data should not be placed in source code, logs, Git repositories, or the browser's local storage. Production tokens belong in encrypted server-side secret storage.
