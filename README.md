# Ankitji PDF Tools

A Python Flask starter project for PDF tools on `ankitji.com`.

## Included Tools

- Merge PDFs
- Split a PDF into one PDF per page
- Compress scanned/image PDFs
- Rotate PDF pages
- Convert images to PDF
- Extract PDF text
- Add text watermark
- Password-protect a PDF

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Production Checklist for ankitji.com

1. Replace `FLASK_SECRET_KEY` with a strong secret environment variable.
2. Put the app behind HTTPS with Nginx, Caddy, Cloudflare, or your hosting provider.
3. Keep upload limits reasonable. The default is `50 MB`; change it with `UPLOAD_LIMIT_MB`.
4. Delete uploaded/temporary files after every request. This starter app processes files in memory.
5. Add rate limiting before public launch.
6. Add virus scanning if anonymous users can upload files.
7. Add privacy text saying files are processed temporarily and not stored.
8. For heavy traffic, move long PDF jobs to a background worker such as Celery/RQ.

## Example Deployment with Gunicorn

Install Gunicorn:

```bash
pip install gunicorn
```

Run:

```bash
FLASK_SECRET_KEY="replace-me" gunicorn -w 2 -b 127.0.0.1:8000 app:app
```

Then point your reverse proxy for `ankitji.com` to `127.0.0.1:8000`.

## Render Deployment

Use these settings on Render:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

Do not use `uvicorn` for this project. This is a Flask app, not a FastAPI/ASGI app.

## Project Structure

```text
.
├── app.py
├── requirements.txt
├── static/
│   └── styles.css
└── templates/
    └── index.html
```
