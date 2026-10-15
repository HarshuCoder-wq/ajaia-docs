# Ajaia Docs

A lightweight collaborative document editor: create, format, import, and share documents with teammates using owner / editor / viewer roles.

**Live app:** `<LIVE_URL>`  ·  **Walkthrough video:** see `VIDEO_URL.txt`

## Test accounts

All passwords: `demo1234` (the login page has one-click fill buttons).

| Email | Use it to |
|---|---|
| alice@ajaia.test | Create documents and share them |
| bob@ajaia.test | Receive a document as **Editor** |
| carol@ajaia.test | Receive a document as **Viewer** |

**2-minute review path:** sign in as Alice → *New document* → type, format, rename → *Share* → add `bob@ajaia.test` (Editor) and `carol@ajaia.test` (Viewer) → sign out → sign in as Bob (can edit, sees it under *Shared with me*) → sign in as Carol (read-only, no toolbar).

## Features

- **Editing:** rich text with H1–H3, bold, italic, underline, strikethrough, bulleted/numbered lists, indent, alignment, quotes, links (Quill 2).
- **Autosave** ~0.8 s after you stop typing, plus `Ctrl/Cmd+S`. Status shows *Unsaved / Saving / All changes saved / Offline — retrying*. Unsaved changes warn before leaving the page.
- **Rename** inline from the title field (Enter saves, Esc cancels).
- **File import:** upload **.txt, .md, or .docx (max 2 MB)** to create a new editable document. Headings, bold/italic and lists are preserved from Markdown and Word. Other types are rejected with a clear message.
- **Sharing:** owner shares by email as **Editor** or **Viewer**, can change roles or revoke. Dashboard separates *My documents* from *Shared with me* with role badges.
- **Conflict safety:** if two people edit the same doc, the second save is rejected (HTTP 409) instead of silently overwriting; the user chooses *Load their version* or *Keep mine*.
- **Delete** (owner only).

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python wsgi.py                                      # http://localhost:5000
```

Uses SQLite (`instance/ajaia_docs.db`) by default; tables and demo users are created on first start. Set `DATABASE_URL` to use Postgres.

| Env var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///ajaia_docs.db` | `postgres://` URLs are accepted |
| `SECRET_KEY` | dev value | **Set in production** |

## Tests

```bash
pytest                    # 21 backend tests: access control, persistence, conflicts, sanitising, import
```

Optional frontend smoke test (runs the real editor JS + Quill in jsdom against a running server):

```bash
python wsgi.py &                       # server on :5000
cd tests/frontend && npm install && npm run smoke
```

## Deploy (Render, free tier)

`render.yaml` is a Render Blueprint that provisions a free web service + free Postgres:

1. Push this folder to a GitHub repo.
2. Render dashboard → **New → Blueprint** → select the repo → **Apply**.
3. Open the service URL. Tables and demo users are created on first boot.

Start command: `gunicorn wsgi:app --workers 2 --preload` (`--preload` makes schema setup run once before workers fork).

> Free-tier note: the service sleeps after inactivity, so the first request can take ~30–50 s.

## Project layout

```
app/
  __init__.py     app factory, config, error handlers
  models.py       User, Document, Share; role_for() = single access check
  auth.py         session login, login_required
  documents.py    pages + JSON API, access enforcement
  content.py      HTML sanitiser + .txt/.md/.docx import
  templates/      Jinja pages (login, dashboard, editor)
  static/         editor.js (Quill, autosave, sharing UI), app.css
tests/            pytest suite + frontend smoke script
```

See `ARCHITECTURE.md` for decisions and tradeoffs, `AI_WORKFLOW.md` for how AI was used.
