from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ROLE_VIEWER = "viewer"
ROLE_EDITOR = "editor"
ROLES = (ROLE_VIEWER, ROLE_EDITOR)

DEMO_PASSWORD = "demo1234"
SEED_USERS = [
    ("alice@ajaia.test", "Alice Owner"),
    ("bob@ajaia.test", "Bob Teammate"),
    ("carol@ajaia.test", "Carol Reviewer"),
]


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="Untitled document")
    # Sanitized HTML produced by the Quill editor. HTML keeps formatting
    # (headings, lists, bold/italic/underline) and renders back losslessly.
    content = db.Column(db.Text, nullable=False, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    # Incremented on every save; used for optimistic concurrency so two editors
    # can't silently overwrite each other.
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = db.relationship("User")
    shares = db.relationship("Share", back_populates="document", cascade="all, delete-orphan")

    def role_for(self, user: "User | None") -> str | None:
        """Return 'owner', 'editor', 'viewer' or None. Single source of truth for access."""
        if user is None:
            return None
        if self.owner_id == user.id:
            return "owner"
        for share in self.shares:
            if share.user_id == user.id:
                return share.role
        return None


class Share(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False, default=ROLE_VIEWER)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    document = db.relationship("Document", back_populates="shares")
    user = db.relationship("User")

    __table_args__ = (db.UniqueConstraint("document_id", "user_id", name="uq_share_doc_user"),)


def seed_users() -> None:
    """Idempotently create the demo accounts reviewers use to test sharing."""
    existing = {u.email for u in User.query.all()}
    for email, name in SEED_USERS:
        if email not in existing:
            user = User(email=email, name=name)
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
    db.session.commit()
