import os

from flask import Flask, jsonify, render_template, request

from .models import db, seed_users


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///ajaia_docs.db")
    # Render/Heroku hand out postgres:// which SQLAlchemy 2 no longer accepts.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=_database_url(),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2 MB upload cap
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from .auth import bp as auth_bp
    from .documents import bp as docs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)

    with app.app_context():
        # Run once per process start. In production gunicorn uses --preload so this
        # runs in the master before workers fork (no create-table race between workers).
        db.create_all()
        seed_users()
        # Don't let forked workers inherit the master's open DB connections.
        db.engine.dispose()

    @app.errorhandler(413)
    def too_large(_e):
        msg = "File is too large. Maximum size is 2 MB."
        if request.path.startswith("/api/"):
            return jsonify(error=msg), 413
        return render_template("error.html", message=msg), 413

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return render_template("error.html", message="Document not found or you don't have access."), 404

    @app.errorhandler(403)
    def forbidden(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="You don't have permission to do that."), 403
        return render_template("error.html", message="You don't have permission to do that."), 403

    return app
