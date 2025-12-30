# WhatsApp Bot (Flask)

A minimal Flask webhook for the WhatsApp Business API that processes incoming messages and responds with features like AI replies (Gemini), image search (Unsplash), reminders, YouTube→MP3 links, and more.

## Features
- Webhook verification and HMAC signature validation
- Message deduplication via Redis
- AI replies using Google Gemini
- Image search via Unsplash
- Stable Diffusion image generation + upload via ImgBB
- Google Sheets balance tracker
- Utility commands: /help, /ai, /bus timetable, /image, /all, /reminder, /youtubemp3, /gen, /money, /balance

## Requirements
- Python 3.10+
- A WhatsApp Business API setup (Cloud API)
- A Meta app with `APP_SECRET` and a `VERIFY_TOKEN`
- A `.env` file with required variables (see `.env.example`)

## Quick Start (Windows PowerShell)

```powershell
# 1) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Create your .env from the example
Copy-Item .env.example .env
# Edit .env and fill in your real values

# 4) Run the app (default port 5000)
python run.py

# Optional: set a custom port
$env:PORT = "8000"; python run.py

# 5) Expose locally via ngrok (adjust to your port)
ngrok http 5000
```

## Webhook Endpoints
- `GET /webhook`: Used by Meta for verification. Must return the challenge when `mode=subscribe` and your `VERIFY_TOKEN` matches.
- `POST /webhook`: Receives WhatsApp events; validated with HMAC using your `APP_SECRET`.

## Environment Variables
Populate these in `.env` (see `.env.example`):
- `ACCESS_TOKEN`: WhatsApp Cloud API token
- `YOUR_PHONE_NUMBER`: Your phone number (if used elsewhere)
- `APP_ID`: Meta app ID
- `APP_SECRET`: Meta app secret (used for HMAC)
- `RECIPIENT_WAID`: Default recipient WA ID (optional)
- `VERSION`: Graph API version, e.g. `v19.0`
- `PHONE_NUMBER_ID`: Your WhatsApp phone number ID
- `VERIFY_TOKEN`: Token used for webhook verification
- `GEMINI_API_KEY`: Google Generative AI API key
- `REDIS_URL`: e.g. `redis://localhost:6379`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`: If you use AWS features
- `GOOGLE_CLOUD_API_KEY`: If you use Google Cloud APIs
- `UNSPLASH_API_KEY`: For `/image` search
- `STABILITY_AI_API_KEY`: For `/gen` images
- `IMGBB_API_KEY`: For image hosting

## Configuration Notes
- Google Service Account: Place your service account key as `google_cloud.json` in the project root. Ensure it is git-ignored.
- Local Paths: Update the hardcoded paths in `app/utils/whatsapp_utils.py`:
  - `image_storage_path`: [app/utils/whatsapp_utils.py#L34](app/utils/whatsapp_utils.py#L34)
- `send_message_outside_app`: Replace the placeholder `GRAPH_API_URL_` string with your actual Graph API URL if you intend to use this function.
- Google Sheets: Replace `Google_Sheet_ID_Here` in the money functions with your sheet ID directly in code.

## Security
- Secrets are loaded via environment variables using `python-dotenv`.
- Signatures are validated with `APP_SECRET` HMAC SHA-256.
- Avoid committing real secrets. Prefer adding `.env`, `google_cloud.json`, and credential files to your `.gitignore`.

## Development Tips
- Use a dedicated Redis instance in production. For local dev, `redis://localhost:6379` is fine.
- Rate limiting and external API quotas (Unsplash/Stability) may apply.
- Keep logs sanitized; avoid printing tokens.

## Troubleshooting
- Webhook verification failing: Check `VERIFY_TOKEN` and that your ngrok/public URL is reachable.
- 403 on POST webhook: Ensure `X-Hub-Signature-256` header is present and your `APP_SECRET` matches.
- Gemini responses empty: Validate `GEMINI_API_KEY` and model availability.
- Image generation/upload errors: Confirm `STABILITY_AI_API_KEY` and `IMGBB_API_KEY` validity.

## License
This repository contains application code; ensure external keys and data remain private. Adjust for your deployment needs.
