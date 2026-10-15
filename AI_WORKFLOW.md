# AI workflow note

> **Before submitting:** review and edit this note so it describes *your* process truthfully. Add anything you changed yourself.

## Tools used

- **Claude (Anthropic)** in an agentic coding workspace: scaffolding, writing the Flask app, editor JS, tests, and docs drafts, plus running tests and a local server.

## Where AI materially sped things up

- Scaffolding the Flask app factory, models, blueprints and Jinja templates in minutes.
- Writing the test suite: access-control matrix (owner/editor/viewer/stranger), validation and import edge cases.
- Wiring Quill 2 (toolbar config, read-only mode, loading imported HTML through Quill's clipboard converter).
- Drafting the README / architecture note, which I then edited.

## What AI output was changed or rejected

- **Gunicorn boot crash.** The first version created tables inside `create_app()`. Running with 2 workers in a smoke test crashed: both workers ran `CREATE TABLE` concurrently. Fixed with `--preload` and disposing the DB pool before fork. Tests alone (single process) did not catch this; running the real server did.
- **Stored HTML contained editor junk.** A headless run of the real editor showed Quill 2 injects `<span class="ql-ui">` list markers that were being saved. Tightened the sanitiser allow-list to drop `<span>`.
- **Text decoding.** An early `.txt` import fell back to UTF-16 for any non-UTF-8 file, which "succeeds" on random bytes and produces garbage. Changed to UTF-16 only when a BOM is present; otherwise show a clear "save as UTF-8" error.
- **Rejected:** real-time collaboration (CRDT/websockets) — too large for the timebox; chose optimistic locking (409 + user choice) so shared editing can't silently lose work.
- **Rejected:** trusting the editor's HTML. Sanitising happens on the server for every save and import.

## How correctness, UX and reliability were verified

- **21 pytest tests** through the HTTP layer: auth required, 404 for unshared docs, viewer can't edit/reshare/delete, editor can't manage sharing, role change + revoke, stale-version 409, XSS stripping, formatting preserved, import of real `.docx` (generated with python-docx) and `.md`, bad-file errors.
- **Real server smoke test** with gunicorn (2 workers) + curl: login, create, rename, 404 page, static assets.
- **Frontend smoke test** (`tests/frontend/editor_smoke.js`): runs the real Quill 2 + `editor.js` in jsdom against the running server and checks imported lists load, typing autosaves, title rename saves, the conflict banner appears when another user saves first, viewers get no toolbar and a non-editable editor, and the share list renders roles.
- **Manual pass in a browser** on the deployed URL: `<add what you checked — formatting toolbar, mobile width, sharing between the three accounts>`.
