"""Roster management endpoints: member reads, admin writes, linked-user guard."""
from app import models


def _person(db, name="Suzuki Taro", **kw):
    person = models.Person(name=name, **kw)
    db.add(person)
    db.commit()
    return person


class TestRead:
    def test_anonymous_401(self, anon_client):
        assert anon_client.get("/people").status_code == 401

    def test_member_lists_people_sorted(self, member_client, db):
        _person(db, "Tanaka", team="Platform")
        _person(db, "Abe", team="Apps")
        names = [p["name"] for p in member_client.get("/people").json()]
        assert names == ["Abe", "Tanaka"]


class TestWrite:
    def test_member_and_manager_cannot_write(self, member_client, manager_client):
        body = {"name": "New Person"}
        assert member_client.post("/people", json=body).status_code == 403
        assert manager_client.post("/people", json=body).status_code == 403
        assert member_client.put("/people/1", json=body).status_code == 403
        assert manager_client.delete("/people/1").status_code == 403

    def test_admin_crud_roundtrip(self, client):
        r = client.post("/people", json={
            "name": "Suzuki Taro", "name_ja": "鈴木太郎", "team": "Platform", "department": "R&D",
        })
        assert r.status_code == 201
        pid = r.json()["id"]
        assert r.json()["name_ja"] == "鈴木太郎"
        r = client.put(f"/people/{pid}", json={"name": "Suzuki Taro", "team": "Apps"})
        assert r.status_code == 200
        assert r.json()["team"] == "Apps"
        assert r.json()["name_ja"] is None  # PUT is whole-object, not partial
        assert client.delete(f"/people/{pid}").status_code == 204
        assert client.get("/people").json() == []

    def test_duplicate_name_409(self, client, db):
        _person(db)
        assert client.post("/people", json={"name": "Suzuki Taro"}).status_code == 409

    def test_rename_onto_existing_name_409(self, client, db):
        _person(db, "A")
        other = _person(db, "B")
        r = client.put(f"/people/{other.id}", json={"name": "A"})
        assert r.status_code == 409

    def test_rename_keeping_own_name_ok(self, client, db):
        person = _person(db, "A")
        assert client.put(f"/people/{person.id}", json={"name": "A", "team": "X"}).status_code == 200

    def test_missing_person_404(self, client):
        assert client.put("/people/999", json={"name": "X"}).status_code == 404
        assert client.delete("/people/999").status_code == 404


class TestLinkedUserGuard:
    def test_delete_blocked_while_user_linked(self, client, db):
        person = _person(db)
        user = db.query(models.User).filter_by(username="member").one()
        user.person_id = person.id
        db.commit()
        r = client.delete(f"/people/{person.id}")
        assert r.status_code == 409
        # Unlink, then the delete goes through.
        uid = user.id
        assert client.put(f"/auth/users/{uid}", json={"clear_person": True}).status_code == 200
        assert client.delete(f"/people/{person.id}").status_code == 204
