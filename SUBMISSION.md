# Submission — Ajaia Docs

**Candidate:** Harsh Sahni (sahnih514@gmail.com)

| Item | Where |
|---|---|
| Live app | `<LIVE_URL>` |
| Walkthrough video | `VIDEO_URL.txt` |
| Source code | `app/`, `wsgi.py`, `requirements.txt`, `render.yaml` |
| Setup & run instructions | `README.md` |
| Architecture note | `ARCHITECTURE.md` |
| AI workflow note | `AI_WORKFLOW.md` |
| Automated tests | `tests/` (pytest) + `tests/frontend/` (editor smoke test) |
| Test accounts | alice@ajaia.test, bob@ajaia.test, carol@ajaia.test — password `demo1234` |

## Status

**Working end to end**
- Create, rename, edit, autosave, reopen documents with rich-text formatting
- Import .txt / .md / .docx (≤ 2 MB) into a new document, structure preserved
- Share by email as Editor or Viewer; change role; revoke; owned vs shared sections on dashboard
- Viewer is read-only (UI and API); non-shared documents return 404
- Conflict detection when two users save the same document
- Persistence in Postgres (deployed) / SQLite (local)

**Intentionally not built** — real-time co-editing, comments, version history, export, sign-up / password reset, CSRF tokens, migrations. Reasoning in `ARCHITECTURE.md`.

**Next 2–4 hours** — version history with restore, Markdown/PDF export, presence indicator, CSRF + migrations.
