from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for

from .auth import login_required
from .content import SUPPORTED_LABEL, FileImportError, clean_title, import_file, sanitize_html
from .models import ROLE_EDITOR, ROLES, Document, Share, User, db

bp = Blueprint("documents", __name__)

# What each access level is allowed to do.
_CAN = {
    "view": {"owner", "editor", "viewer"},
    "edit": {"owner", "editor"},
    "own": {"owner"},
}


def get_document(doc_id: int, need: str = "view") -> tuple[Document, str]:
    """Load a document and enforce access.

    No access at all -> 404, so we don't reveal that a document exists.
    Some access but not enough -> 403.
    """
    doc = db.session.get(Document, doc_id)
    role = doc.role_for(g.user) if doc else None
    if role is None:
        abort(404)
    if role not in _CAN[need]:
        abort(403)
    return doc, role


def doc_json(doc: Document, role: str) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "version": doc.version,
        "role": role,
        "owner": {"name": doc.owner.name, "email": doc.owner.email},
        "updated_at": doc.updated_at.isoformat(),
    }


def share_json(share: Share) -> dict:
    return {"id": share.id, "email": share.user.email, "name": share.user.name, "role": share.role}


# ---------------------------------------------------------------- pages


@bp.route("/")
@login_required
def dashboard():
    owned = (
        Document.query.filter_by(owner_id=g.user.id).order_by(Document.updated_at.desc()).all()
    )
    shared = (
        db.session.query(Document, Share.role)
        .join(Share, Share.document_id == Document.id)
        .filter(Share.user_id == g.user.id)
        .order_by(Document.updated_at.desc())
        .all()
    )
    return render_template("dashboard.html", owned=owned, shared=shared, supported=SUPPORTED_LABEL)


@bp.route("/documents", methods=["POST"])
@login_required
def create():
    doc = Document(title="Untitled document", content="", owner_id=g.user.id)
    db.session.add(doc)
    db.session.commit()
    return redirect(url_for("documents.editor", doc_id=doc.id))


@bp.route("/documents/import", methods=["POST"])
@login_required
def import_document():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Choose a file to import.", "error")
        return redirect(url_for("documents.dashboard"))
    try:
        title, body = import_file(upload.filename, upload.read())
    except FileImportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("documents.dashboard"))
    doc = Document(title=title, content=body, owner_id=g.user.id)
    db.session.add(doc)
    db.session.commit()
    flash(f"Imported “{upload.filename}” as a new document.", "success")
    return redirect(url_for("documents.editor", doc_id=doc.id))


@bp.route("/documents/<int:doc_id>")
@login_required
def editor(doc_id: int):
    doc, role = get_document(doc_id, "view")
    return render_template("editor.html", doc=doc, role=role, doc_data=doc_json(doc, role))


@bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete(doc_id: int):
    doc, _ = get_document(doc_id, "own")
    db.session.delete(doc)
    db.session.commit()
    flash(f"Deleted “{doc.title}”.", "success")
    return redirect(url_for("documents.dashboard"))


# ---------------------------------------------------------------- JSON API


@bp.route("/api/documents/<int:doc_id>", methods=["GET"])
@login_required
def api_get(doc_id: int):
    doc, role = get_document(doc_id, "view")
    return jsonify(doc_json(doc, role))


@bp.route("/api/documents/<int:doc_id>", methods=["PATCH"])
@login_required
def api_update(doc_id: int):
    doc, role = get_document(doc_id, "edit")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Expected a JSON body."), 400

    base_version = payload.get("version")
    if not isinstance(base_version, int):
        return jsonify(error="'version' is required."), 400
    if base_version != doc.version:
        # Someone else saved since this client loaded the doc.
        return jsonify(error="This document was changed by someone else.", current=doc_json(doc, role)), 409

    if "title" not in payload and "content" not in payload:
        return jsonify(error="Nothing to update."), 400
    if "title" in payload:
        try:
            doc.title = clean_title(payload["title"])
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    if "content" in payload:
        if not isinstance(payload["content"], str):
            return jsonify(error="'content' must be a string."), 400
        if len(payload["content"]) > 1_000_000:
            return jsonify(error="Document is too large (1 MB of formatted text max)."), 400
        doc.content = sanitize_html(payload["content"])

    doc.version += 1
    db.session.commit()
    return jsonify(doc_json(doc, role))


@bp.route("/api/documents/<int:doc_id>/shares", methods=["GET"])
@login_required
def api_list_shares(doc_id: int):
    doc, _ = get_document(doc_id, "own")
    return jsonify(shares=[share_json(s) for s in doc.shares])


@bp.route("/api/documents/<int:doc_id>/shares", methods=["POST"])
@login_required
def api_share(doc_id: int):
    """Grant access, or change the role if the user already has access."""
    doc, _ = get_document(doc_id, "own")
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email") or "").strip().lower()
    role = payload.get("role") or ROLE_EDITOR

    if not email:
        return jsonify(error="Enter an email address."), 400
    if role not in ROLES:
        return jsonify(error=f"Role must be one of: {', '.join(ROLES)}."), 400
    target = User.query.filter_by(email=email).first()
    if target is None:
        return jsonify(error=f"No user with email {email}."), 404
    if target.id == doc.owner_id:
        return jsonify(error="You already own this document."), 400

    share = Share.query.filter_by(document_id=doc.id, user_id=target.id).first()
    created = share is None
    if created:
        share = Share(document_id=doc.id, user_id=target.id, role=role)
        db.session.add(share)
    else:
        share.role = role
    db.session.commit()
    return jsonify(share_json(share)), 201 if created else 200


@bp.route("/api/documents/<int:doc_id>/shares/<int:share_id>", methods=["DELETE"])
@login_required
def api_unshare(doc_id: int, share_id: int):
    doc, _ = get_document(doc_id, "own")
    share = Share.query.filter_by(id=share_id, document_id=doc.id).first()
    if share is None:
        abort(404)
    db.session.delete(share)
    db.session.commit()
    return "", 204
