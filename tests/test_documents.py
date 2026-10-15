"""End-to-end tests through the HTTP layer: the access rules are the part most
likely to break silently, so most of the coverage is there."""

from conftest import new_doc


def save(client, doc_id, version, **fields):
    return client.patch(f"/api/documents/{doc_id}", json={"version": version, **fields})


# ------------------------------------------------------------ auth


def test_requires_login(app):
    c = app.test_client()
    assert c.get("/").status_code == 302
    assert c.get("/api/documents/1").status_code == 401


def test_bad_password_rejected(app):
    c = app.test_client()
    res = c.post("/login", data={"email": "alice@ajaia.test", "password": "nope"})
    assert res.status_code == 200 and b"Invalid email or password" in res.data


# ------------------------------------------------------------ create / edit / persist


def test_create_rename_edit_and_reopen(alice):
    doc_id = new_doc(alice)
    res = save(alice, doc_id, 1, title="  Q4   plan ", content="<h1>Goals</h1><p><strong>Ship</strong> it</p>")
    assert res.status_code == 200
    assert res.json["title"] == "Q4 plan"  # whitespace normalised
    assert res.json["version"] == 2

    reopened = alice.get(f"/api/documents/{doc_id}").json
    assert reopened["content"] == "<h1>Goals</h1><p><strong>Ship</strong> it</p>"
    assert b"Q4 plan" in alice.get("/").data


def test_formatting_is_preserved_and_scripts_are_stripped(alice):
    doc_id = new_doc(alice)
    html = (
        '<p class="ql-align-center"><u>u</u> <em>i</em></p>'
        '<ol><li data-list="bullet">a</li><li data-list="ordered">b</li></ol>'
        '<p onclick="x()">hi<script>alert(1)</script></p>'
        '<a href="javascript:alert(1)">bad</a>'
    )
    content = save(alice, doc_id, 1, content=html).json["content"]
    assert '<p class="ql-align-center"><u>u</u> <em>i</em></p>' in content
    assert 'data-list="bullet"' in content and 'data-list="ordered"' in content
    assert "script" not in content and "onclick" not in content and "javascript:" not in content


def test_validation_errors(alice):
    doc_id = new_doc(alice)
    assert save(alice, doc_id, 1, title="   ").status_code == 400
    assert save(alice, doc_id, 1, title="x" * 201).status_code == 400
    assert save(alice, doc_id, 1).status_code == 400  # nothing to update
    assert alice.patch(f"/api/documents/{doc_id}", json={"title": "no version"}).status_code == 400
    assert alice.patch(f"/api/documents/{doc_id}", data="not json").status_code == 400


def test_stale_version_is_rejected_with_conflict(alice, bob):
    doc_id = new_doc(alice)
    alice.post(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test", "role": "editor"})

    assert save(alice, doc_id, 1, content="<p>alice</p>").status_code == 200
    res = save(bob, doc_id, 1, content="<p>bob, from a stale tab</p>")
    assert res.status_code == 409
    assert res.json["current"]["content"] == "<p>alice</p>"  # nothing overwritten


# ------------------------------------------------------------ sharing / access control


def test_unshared_document_is_invisible(alice, bob):
    doc_id = new_doc(alice)
    # 404, not 403: don't leak that the document exists.
    assert bob.get(f"/documents/{doc_id}").status_code == 404
    assert bob.get(f"/api/documents/{doc_id}").status_code == 404
    assert save(bob, doc_id, 1, content="<p>x</p>").status_code == 404


def test_viewer_can_read_but_not_edit_or_reshare(alice, carol):
    doc_id = new_doc(alice)
    save(alice, doc_id, 1, title="Budget", content="<p>secret</p>")
    res = alice.post(f"/api/documents/{doc_id}/shares", json={"email": "carol@ajaia.test", "role": "viewer"})
    assert res.status_code == 201

    page = carol.get("/").data.decode()
    assert "Shared with me" in page and "Budget" in page and "Viewer" in page
    assert carol.get(f"/api/documents/{doc_id}").json["role"] == "viewer"
    assert save(carol, doc_id, 2, content="<p>hacked</p>").status_code == 403
    assert carol.post(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test"}).status_code == 403
    assert carol.post(f"/documents/{doc_id}/delete").status_code == 403


def test_editor_can_edit_but_not_manage_sharing(alice, bob):
    doc_id = new_doc(alice)
    alice.post(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test", "role": "editor"})
    assert save(bob, doc_id, 1, content="<p>bob was here</p>").status_code == 200
    assert alice.get(f"/api/documents/{doc_id}").json["content"] == "<p>bob was here</p>"
    assert bob.get(f"/api/documents/{doc_id}/shares").status_code == 403


def test_role_change_and_revoke(alice, bob):
    doc_id = new_doc(alice)
    share = alice.post(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test", "role": "editor"}).json
    # Re-sharing updates the role instead of duplicating.
    res = alice.post(f"/api/documents/{doc_id}/shares", json={"email": "BOB@ajaia.test", "role": "viewer"})
    assert res.status_code == 200 and res.json["role"] == "viewer"
    assert len(alice.get(f"/api/documents/{doc_id}/shares").json["shares"]) == 1
    assert save(bob, doc_id, 1, content="<p>x</p>").status_code == 403

    assert alice.delete(f"/api/documents/{doc_id}/shares/{share['id']}").status_code == 204
    assert bob.get(f"/api/documents/{doc_id}").status_code == 404


def test_share_validation(alice):
    doc_id = new_doc(alice)
    url = f"/api/documents/{doc_id}/shares"
    assert alice.post(url, json={"email": ""}).status_code == 400
    assert alice.post(url, json={"email": "ghost@ajaia.test"}).status_code == 404
    assert alice.post(url, json={"email": "alice@ajaia.test"}).status_code == 400
    assert alice.post(url, json={"email": "bob@ajaia.test", "role": "admin"}).status_code == 400


def test_owner_can_delete(alice, bob):
    doc_id = new_doc(alice)
    alice.post(f"/api/documents/{doc_id}/shares", json={"email": "bob@ajaia.test"})
    assert alice.post(f"/documents/{doc_id}/delete").status_code == 302
    assert alice.get(f"/api/documents/{doc_id}").status_code == 404
    assert bob.get(f"/api/documents/{doc_id}").status_code == 404
