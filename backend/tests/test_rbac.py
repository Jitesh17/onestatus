"""Role enforcement: default-deny route walk, the role matrix, author forcing,
and saved-view ownership. The conftest seeds one account per role (username ==
role, password "pw"); client fixtures arrive already logged in.
"""
from app import models
from app.main import app

# The ONLY routes an anonymous client may reach. Anything else must 401, so a new
# endpoint added without thinking about auth fails the walk below instead of
# shipping open.
PUBLIC = {("GET", "/health"), ("POST", "/auth/login")}


class TestDefaultDeny:
    def test_every_route_outside_allowlist_401s_anonymously(self, anon_client):
        checked = 0
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            if not path or path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
                continue
            for method in methods - {"HEAD", "OPTIONS"}:
                if (method, path) in PUBLIC:
                    continue
                # Fill path params with a dummy id; auth runs before path handling
                # for 401 purposes only when the param parses, so use an int.
                url = path.replace("{view_id}", "1").replace("{user_id}", "1").replace("{person_id}", "1")
                r = anon_client.request(method, url)
                checked += 1
                assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"
        assert checked >= 15  # the walk actually walked something

    def test_health_is_public(self, anon_client):
        assert anon_client.get("/health").status_code == 200


class TestRoleMatrix:
    def test_member_reads_but_cannot_create_projects(self, member_client):
        assert member_client.get("/projects").status_code == 200
        r = member_client.post("/projects", json={"name": "P"})
        assert r.status_code == 403

    def test_manager_creates_projects_and_tasks(self, manager_client):
        r = manager_client.post("/projects", json={"name": "P"})
        assert r.status_code == 201
        pid = r.json()["id"]
        r = manager_client.post("/tasks", json={"project_id": pid, "title": "T"})
        assert r.status_code == 201

    def test_member_cannot_create_tasks(self, member_client):
        assert member_client.post("/tasks", json={"project_id": 1, "title": "T"}).status_code == 403

    def test_member_reads_settings_but_cannot_write(self, member_client):
        assert member_client.get("/settings").status_code == 200
        assert member_client.put("/settings", json={"llm_model": "x"}).status_code == 403
        assert member_client.get("/settings/models").status_code == 403

    def test_manager_cannot_write_settings(self, manager_client):
        assert manager_client.put("/settings", json={"llm_model": "x"}).status_code == 403

    def test_admin_writes_settings(self, client):
        assert client.put("/settings", json={"llm_temperature": 0.5}).status_code == 200

    def test_member_sees_dashboard(self, member_client):
        assert member_client.get("/dashboard").status_code == 200


class TestAuthorForcing:
    def _task(self, client):
        pid = client.post("/projects", json={"name": "P"}).json()["id"]
        return client.post("/tasks", json={"project_id": pid, "title": "T"}).json()["id"]

    def test_member_author_is_forced_to_self(self, client, member_client):
        tid = self._task(client)
        r = member_client.post("/updates", json={
            "task_id": tid, "raw_text": "did things", "author": "Somebody Else",
        })
        assert r.status_code == 201
        assert r.json()["author"] == "member"

    def test_member_author_uses_linked_person_name(self, client, db):
        person = models.Person(name="Suzuki Taro")
        db.add(person)
        db.commit()
        member = db.query(models.User).filter_by(username="member").one()
        member.person_id = person.id
        db.commit()
        tid = self._task(client)
        from tests.conftest import login
        from fastapi.testclient import TestClient
        from app.main import app as theapp
        with TestClient(theapp) as c:
            login(c, "member")
            r = c.post("/updates", json={"task_id": tid, "raw_text": "x"})
        assert r.json()["author"] == "Suzuki Taro"

    def test_manager_may_override_author(self, client, manager_client):
        tid = self._task(client)
        r = manager_client.post("/updates", json={
            "task_id": tid, "raw_text": "on their behalf", "author": "Suzuki Taro",
        })
        assert r.json()["author"] == "Suzuki Taro"

    def test_manager_without_author_posts_as_self(self, client, manager_client):
        tid = self._task(client)
        r = manager_client.post("/updates", json={"task_id": tid, "raw_text": "x"})
        assert r.json()["author"] == "manager"


class TestViewOwnership:
    _CONFIG = {"summary": ""}

    def test_create_stamps_creator(self, member_client, db):
        r = member_client.post("/views", json={"name": "mine", "config": self._CONFIG})
        assert r.status_code == 201
        member_id = db.query(models.User).filter_by(username="member").one().id
        assert r.json()["created_by"] == member_id

    def test_creator_deletes_own_view(self, member_client):
        vid = member_client.post("/views", json={"name": "mine", "config": self._CONFIG}).json()["id"]
        assert member_client.delete(f"/views/{vid}").status_code == 204

    def test_other_member_cannot_delete(self, member_client, client, db):
        vid = client.post("/views", json={"name": "admins", "config": self._CONFIG}).json()["id"]
        assert member_client.delete(f"/views/{vid}").status_code == 403

    def test_manager_deletes_any_view(self, member_client, manager_client):
        vid = member_client.post("/views", json={"name": "mine", "config": self._CONFIG}).json()["id"]
        assert manager_client.delete(f"/views/{vid}").status_code == 204

    def test_legacy_view_without_creator_needs_manager(self, member_client, manager_client, db):
        from app import crud
        legacy = crud.create_view(db, "pre-auth", self._CONFIG)  # created_by stays NULL
        assert member_client.delete(f"/views/{legacy.id}").status_code == 403
        assert manager_client.delete(f"/views/{legacy.id}").status_code == 204

    def test_missing_view_404s(self, client):
        assert client.delete("/views/999").status_code == 404
