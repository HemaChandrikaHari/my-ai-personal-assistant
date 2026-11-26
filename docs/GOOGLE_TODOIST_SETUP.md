# Google and Todoist OAuth setup

These instructions register the OAuth clients that the application needs. Do not paste client secrets or encryption keys into GitHub issues, source files, or chat.

## 1. Generate the token-encryption key

From the repository root, run:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output to `TOKEN_ENCRYPTION_KEY` in your local `.env`. Back it up in a secure password manager or secret manager. The application cannot decrypt saved OAuth tokens if this key is lost or rotated without re-encrypting them.

## 2. Register the Google OAuth client

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **Gmail API** and **Google Calendar API**.
4. Configure the OAuth consent screen and add your own Google account as a test user while the app is in testing.
5. Create an OAuth client ID with application type **Web application**.
6. Add this authorized redirect URI exactly: `http://localhost:8000/api/v1/oauth/google/callback`.
7. Copy the client ID and client secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
8. Set `GOOGLE_REDIRECT_URI` to the same exact callback URL.

The app requests Gmail read-only access and Google Calendar event access. Gmail content is not sent unless you ask the assistant to read it. Review Google's OAuth verification requirements before allowing external users.

## 3. Register the Todoist OAuth app

1. Open [Todoist App Management](https://developer.todoist.com/appconsole.html).
2. Create an app and set its redirect URL to `http://localhost:8000/api/v1/oauth/todoist/callback`.
3. Copy the client ID and client secret into `TODOIST_CLIENT_ID` and `TODOIST_CLIENT_SECRET`.
4. Set `TODOIST_REDIRECT_URI` to the same exact callback URL.

The app requests `data:read_write`. The assistant chat only receives the read-only task-list tool. Task creation is a separate API call initiated by the dashboard's explicit Create button and browser confirmation.

## 4. Start locally

Copy `.env.example` to `.env`, fill in the values above, set `OPENAI_API_KEY` if you want AI chat, and run:

```bash
docker compose up --build
```

Open `http://localhost:3000`, connect Google and Todoist, and approve each provider's consent screen. The dashboard should then show each connected account and allow loading Gmail message IDs, upcoming calendar events, and Todoist tasks.

## 6. Run read-only live integration checks

After connecting both accounts, install the backend requirements and run the smoke test. It checks API health, OAuth connection state, Gmail message metadata, upcoming Calendar events, and Todoist tasks. It deliberately does not print private content or create/modify/send/delete anything.

Local development:

```bash
pip install -r backend/requirements.txt
ASSISTANT_API_URL=http://localhost:8000 ASSISTANT_USER_ID=local-developer python scripts/live_integration_smoke.py
```

For a deployed environment, use a short-lived API access token from your configured OIDC provider:

```bash
ASSISTANT_API_URL=https://your-api-domain.example \
ASSISTANT_BEARER_TOKEN="$YOUR_SHORT_LIVED_ACCESS_TOKEN" \
python scripts/live_integration_smoke.py --check-blueticks
```

Do not put tokens in shell history or commit them. The optional Blueticks check only discovers tool names; it does not invoke any WhatsApp tool or send messages. A successful run proves live read access for the connected accounts, not write permissions. Test Calendar event creation and Todoist task creation manually from the dashboard after reviewing the confirmation prompt.

## 5. Production requirements

- Use HTTPS callback URLs and register the exact production URLs with each provider.
- Put provider client secrets and `TOKEN_ENCRYPTION_KEY` in AWS Secrets Manager or an equivalent secret manager; do not use the local `.env` file.
- Keep the encryption key stable across deployments and backups.
- Configure `FRONTEND_URL`, `CORS_ORIGINS`, `GOOGLE_REDIRECT_URI`, and `TODOIST_REDIRECT_URI` for the production domains.
- Set `APP_ENV=production`, `NEXT_PUBLIC_ENABLE_DEV_AUTH=false`, and the OIDC issuer, audience, and JWKS URL.
- Apply the Alembic migrations before starting the API.
- Complete Google's OAuth consent verification if the app is made available beyond test users.
