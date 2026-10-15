from functools import wraps

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for

from .models import DEMO_PASSWORD, SEED_USERS, User, db

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_user():
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Not signed in"), 401
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            nxt = request.args.get("next") or ""
            # Only allow local redirects.
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = url_for("documents.dashboard")
            return redirect(nxt)
        flash("Invalid email or password.", "error")
    return render_template("login.html", demo_users=SEED_USERS, demo_password=DEMO_PASSWORD)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
