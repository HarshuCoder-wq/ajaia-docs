import pytest

from app import create_app
from app.models import DEMO_PASSWORD, db


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "SECRET_KEY": "test",
    })
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def login(app):
    """Return a factory giving a logged-in test client for a seeded user."""

    def _login(email):
        client = app.test_client()
        res = client.post("/login", data={"email": email, "password": DEMO_PASSWORD})
        assert res.status_code == 302, "seeded login should redirect"
        return client

    return _login


@pytest.fixture
def alice(login):
    return login("alice@ajaia.test")


@pytest.fixture
def bob(login):
    return login("bob@ajaia.test")


@pytest.fixture
def carol(login):
    return login("carol@ajaia.test")


def new_doc(client) -> int:
    res = client.post("/documents")
    assert res.status_code == 302
    return int(res.headers["Location"].rstrip("/").split("/")[-1])
