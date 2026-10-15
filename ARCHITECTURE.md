# Architecture note

## Shape

Server-rendered Flask app with a small JSON API for the editor.

```
Browser ── Jinja pages (login, dashboard, editor)
   │
   └─ editor.js (Quill 2) ── PATCH /api/documents/:id         save title/content (+version)
                          ── GET/POST/DELETE …/shares         owner manages access
Flask ── documents.py: get_document(id, need) ─► Document.role_for(user)  (one access check)
      ── content.py: sanitize_html(), import_file()
      ── SQLAlchemy ─► SQLite (local) / Postgres (Render)
```

**Data model:** `User`, `Document(owner_id, title, content HTML, version)`, `Share(document_id, user_id, role)` with a unique (document, user) constraint.

## What I prioritised, and why

1. **Correct access control over feature count.** Sharing is the part reviewers can break, and the part that matters most in a real team tool. Every route goes through one function, `get_document(id, need)`, backed by `Document.role_for(user)`. No access returns **404** (don't reveal the doc exists); insufficient role returns **403**. Most of the test suite targets this.
2. **Server-side HTML sanitising.** Content written by one user renders in another user's browser, so the server cleans everything (editor saves *and* file imports) with an allow-list (`nh3`) of exactly the tags/classes the editor produces. Trusting the client here would be a stored-XSS hole.
3. **A save model that doesn't lose work.** Autosave with a single in-flight request and merged pending edits, offline retry, and **optimistic concurrency** (`version` column → 409 on stale save). Real-time co-editing was out of scope, but two people with the same doc open is the first thing that happens once sharing exists, and silent overwrite is the worst outcome.
4. **Import that preserves structure.** .docx via `mammoth` (semantic HTML: headings, lists, bold/italic), .md via `markdown`, .txt as escaped paragraphs. Output goes through the same sanitiser.

## Key decisions

| Decision | Why | Tradeoff |
|---|---|---|
| Store content as sanitised HTML | Round-trips through Quill losslessly, readable in the DB, trivial to export later | Less structured than Quill Delta JSON; diffing/OT would want Delta |
| Quill 2 from CDN, no JS build | Zero frontend toolchain; fast to ship and run | No bundling/TS; fine at this size |
| Seeded users + session login | Reviewers need to switch users quickly; real auth adds nothing to the evaluation | No sign-up, password reset, or SSO |
| Viewer / Editor roles (stretch) | Deepens the sharing model where it matters | No "commenter" role |
| Optimistic locking, not CRDT | Hours vs days; prevents data loss | Users resolve conflicts manually instead of merging |
| `gunicorn --preload` | Found a real race: two workers ran `create_all` concurrently and crashed on boot | Schema setup at boot instead of migrations |
| Render Blueprint + Postgres | Free, one-click, persistent DB (Render's free disk is ephemeral, so SQLite would reset) | Cold starts on free tier |

## Deliberately not built

- Real-time collaboration / presence (would need websockets + CRDT/OT).
- Comments, suggestion mode, version history, export.
- Sign-up, password reset, email invitations to non-users (sharing targets existing accounts).
- Attachments stored alongside a document (import-to-new-doc was the more product-relevant flow).
- DB migrations (Alembic) — `create_all` is enough for a fresh schema.
- CSRF tokens: forms are same-origin with `SameSite=Lax` session cookies and the API requires JSON. Would add Flask-WTF CSRF before production.

## Next 2–4 hours

1. Version history: snapshot table written on save (throttled), restore button. Reuses the version column.
2. Export to Markdown / PDF.
3. Presence indicator ("Bob is viewing") via polling, then websockets.
4. Alembic migrations, CSRF tokens, rate limiting on login.
