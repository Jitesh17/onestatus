"""Auth core: hashing, sessions, the /auth API, bootstrap, and the CLI."""
import datetime as dt

from sqlalchemy import inspect

from app import auth, create_admin, models
from app.database import engine


class TestPasswordHashing:
    def test_roundtrip(self):
        h = auth.hash_password("hunter2!")
        assert h != "hunter2!"
        assert auth.verify_password("hunter2!", h)

    def test_wrong_password(self):
        h = auth.hash_password("hunter2!")
        assert not auth.verify_password("hunter3!", h)

    def test_garbage_hash_is_false_not_error(self):
        assert not auth.verify_password("x", "not-a-bcrypt-hash")

    def test_hashes_are_salted(self):
        assert auth.hash_password("same") != auth.hash_password("same")


def _user(db, username="u1", role="member", **kw):
    user = models.User(username=username, password_hash=auth.hash_password("pw"), role=role, **kw)
    db.add(user)
    db.commit()
    return user


class TestSessionLifecycle:
    def test_create_and_resolve(self, db):
        user = _user(db)
        token = auth.create_session(db, user)
        assert auth.resolve_session(db, token).id == user.id

    def test_token_not_stored_raw(self, db):
        token = auth.create_session(db, _user(db))
        rows = db.query(models.AuthSession).all()
        assert len(rows) == 1
        assert token not in rows[0].token_hash

    def test_revoke(self, db):
        user = _user(db)
        token = auth.create_session(db, user)
        auth.revoke_session(db, token)
        assert auth.resolve_session(db, token) is None

    def test_expired_session_rejected(self, db):
        user = _user(db)
        token = auth.create_session(db, user)
        db.query(models.AuthSession).update(
            {"expires_at": dt.datetime.utcnow() - dt.timedelta(seconds=1)}
        )
        db.commit()
        assert auth.resolve_session(db, token) is None

    def test_inactive_user_rejected(self, db):
        user = _user(db)
        token = auth.create_session(db, user)
        user.is_active = False
        db.commit()
        assert auth.resolve_session(db, token) is None

    def test_unknown_token(self, db):
        assert auth.resolve_session(db, "nope") is None

    def test_expired_rows_purged_on_login(self, db):
        user = _user(db)
        auth.create_session(db, user)
        db.query(models.AuthSession).update(
            {"expires_at": dt.datetime.utcnow() - dt.timedelta(days=1)}
        )
        db.commit()
        auth.create_session(db, user)
        assert db.query(models.AuthSession).count() == 1


class TestRoleFloor:
    def test_hierarchy(self):
        assert models.ROLE_ORDER["member"] < models.ROLE_ORDER["manager"] < models.ROLE_ORDER["admin"]

    def test_author_name_prefers_person(self, db):
        person = models.Person(name="Alex")
        db.add(person)
        db.commit()
        linked = _user(db, username="alex", person_id=person.id)
        db.refresh(linked)
        bare = _user(db, username="solo")
        assert auth.author_name(linked) == "Alex"
        assert auth.author_name(bare) == "solo"


def _login(client, username, password="pw"):
    return client.post("/auth/login", json={"username": username, "password": password})


class TestLoginAPI:
    def test_login_sets_cookie_and_returns_me(self, client, db):
        _user(db, "alice", role="manager")
        r = _login(client, "alice")
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alice"
        assert body["role"] == "manager"
        assert body["author"] == "alice"
        cookie = r.headers["set-cookie"]
        assert auth.SESSION_COOKIE in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie or "samesite=lax" in cookie.lower()
        assert "Path=/" in cookie

    def test_wrong_password_and_unknown_user_same_detail(self, client, db):
        _user(db, "alice")
        bad_pw = _login(client, "alice", "wrong")
        unknown = _login(client, "nobody")
        assert bad_pw.status_code == unknown.status_code == 401
        assert bad_pw.json()["detail"] == unknown.json()["detail"]

    def test_disabled_account_cannot_login(self, client, db):
        _user(db, "alice", is_active=False)
        assert _login(client, "alice").status_code == 401

    def test_me_requires_login(self, anon_client):
        assert anon_client.get("/auth/me").status_code == 401

    def test_me_after_login(self, client, db):
        person = models.Person(name="Alice A")
        db.add(person)
        db.commit()
        _user(db, "alice", person_id=person.id)
        _login(client, "alice")
        body = client.get("/auth/me").json()
        assert body["author"] == "Alice A"
        assert body["person_id"] == person.id

    def test_logout_revokes_session(self, client, db):
        alice = _user(db, "alice")
        _login(client, "alice")
        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/me").status_code == 401
        assert db.query(models.AuthSession).filter_by(user_id=alice.id).count() == 0

    def test_change_my_password(self, client, db):
        _user(db, "alice")
        _login(client, "alice")
        r = client.put("/auth/me/password", json={
            "current_password": "pw", "new_password": "newpass123",
        })
        assert r.status_code == 204
        assert _login(client, "alice", "pw").status_code == 401
        assert _login(client, "alice", "newpass123").status_code == 200

    def test_change_password_wrong_current(self, client, db):
        _user(db, "alice")
        _login(client, "alice")
        r = client.put("/auth/me/password", json={
            "current_password": "nope", "new_password": "newpass123",
        })
        assert r.status_code == 403

    def test_short_new_password_rejected(self, client, db):
        _user(db, "alice")
        _login(client, "alice")
        r = client.put("/auth/me/password", json={
            "current_password": "pw", "new_password": "short",
        })
        assert r.status_code == 422


class TestUsersAdminAPI:
    # The `client` fixture is already logged in as the seeded admin.

    def test_member_cannot_list_users(self, member_client):
        assert member_client.get("/auth/users").status_code == 403

    def test_admin_crud_roundtrip(self, client, db):
        c = client
        r = c.post("/auth/users", json={
            "username": "sam", "password": "password1", "role": "member",
        })
        assert r.status_code == 201
        uid = r.json()["id"]
        assert any(u["username"] == "sam" for u in c.get("/auth/users").json())
        r = c.put(f"/auth/users/{uid}", json={"role": "manager"})
        assert r.json()["role"] == "manager"
        assert c.delete(f"/auth/users/{uid}").status_code == 204

    def test_duplicate_username_409(self, client, db):
        c = client
        body = {"username": "sam", "password": "password1"}
        assert c.post("/auth/users", json=body).status_code == 201
        assert c.post("/auth/users", json=body).status_code == 409

    def test_unknown_person_id_422(self, client, db):
        c = client
        r = c.post("/auth/users", json={
            "username": "sam", "password": "password1", "person_id": 999,
        })
        assert r.status_code == 422

    def test_clear_person_link(self, client, db):
        c = client
        person = models.Person(name="Sam S")
        db.add(person)
        db.commit()
        uid = c.post("/auth/users", json={
            "username": "sam", "password": "password1", "person_id": person.id,
        }).json()["id"]
        r = c.put(f"/auth/users/{uid}", json={"clear_person": True})
        assert r.json()["person_id"] is None

    def test_last_admin_cannot_be_demoted(self, client, db):
        c = client
        boss_id = c.get("/auth/me").json()["id"]
        assert c.put(f"/auth/users/{boss_id}", json={"role": "member"}).status_code == 409
        assert c.put(f"/auth/users/{boss_id}", json={"is_active": False}).status_code == 409
        assert c.delete(f"/auth/users/{boss_id}").status_code == 409

    def test_second_admin_unlocks_demotion(self, client, db):
        c = client
        boss_id = c.get("/auth/me").json()["id"]
        c.post("/auth/users", json={
            "username": "boss2", "password": "password1", "role": "admin",
        })
        assert c.put(f"/auth/users/{boss_id}", json={"role": "member"}).status_code == 200

    def test_deactivation_kills_live_sessions(self, client, db):
        from fastapi.testclient import TestClient
        from app.main import app
        c = client
        uid = c.post("/auth/users", json={
            "username": "sam", "password": "password1",
        }).json()["id"]
        with TestClient(app) as sam:
            _login(sam, "sam", "password1")
            assert sam.get("/auth/me").status_code == 200
            c.put(f"/auth/users/{uid}", json={"is_active": False})
            assert sam.get("/auth/me").status_code == 401

    def test_admin_resets_user_password(self, client, db):
        c = client
        uid = c.post("/auth/users", json={
            "username": "sam", "password": "password1",
        }).json()["id"]
        r = c.put(f"/auth/users/{uid}/password", json={"new_password": "password2"})
        assert r.status_code == 204
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as sam:
            assert _login(sam, "sam", "password1").status_code == 401
            assert _login(sam, "sam", "password2").status_code == 200


def _empty_users(db):
    # Bootstrap only acts on an EMPTY users table; drop the conftest role accounts.
    db.query(models.User).delete()
    db.commit()


class TestBootstrap:
    def test_creates_admin_from_env(self, db, monkeypatch):
        _empty_users(db)
        monkeypatch.setenv("ADMIN_PASSWORD", "bootpass1")
        monkeypatch.setenv("ADMIN_USER", "chief")
        create_admin.bootstrap_admin(db)
        user = db.query(models.User).one()
        assert (user.username, user.role) == ("chief", "admin")
        assert auth.verify_password("bootpass1", user.password_hash)

    def test_no_env_warns_and_creates_nothing(self, db, monkeypatch, caplog):
        _empty_users(db)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        with caplog.at_level("WARNING", logger="onestatus.auth"):
            create_admin.bootstrap_admin(db)
        assert db.query(models.User).count() == 0
        assert any("ADMIN_PASSWORD" in r.message for r in caplog.records)

    def test_never_touches_populated_table(self, db, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "bootpass1")
        monkeypatch.setenv("ADMIN_USER", "chief")
        before = db.query(models.User).count()
        create_admin.bootstrap_admin(db)
        assert db.query(models.User).count() == before
        assert db.query(models.User).filter_by(username="chief").first() is None


class TestCreateAdminCLI:
    def test_creates_admin(self, db, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["create_admin", "rescue"])
        monkeypatch.setattr("getpass.getpass", lambda prompt: "rescuepass1")
        assert create_admin.main() == 0
        db.expire_all()
        user = db.query(models.User).filter_by(username="rescue").one()
        assert user.role == "admin"
        assert "created" in capsys.readouterr().out

    def test_resets_existing_user_to_active_admin(self, db, monkeypatch, capsys):
        _user(db, "rescue", role="member", is_active=False)
        monkeypatch.setattr("sys.argv", ["create_admin", "rescue"])
        monkeypatch.setattr("getpass.getpass", lambda prompt: "rescuepass1")
        assert create_admin.main() == 0
        db.expire_all()
        user = db.query(models.User).filter_by(username="rescue").one()
        assert user.role == "admin" and user.is_active
        assert auth.verify_password("rescuepass1", user.password_hash)
        assert "reset" in capsys.readouterr().out

    def test_short_password_rejected(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["create_admin"])
        monkeypatch.setattr("getpass.getpass", lambda prompt: "tiny")
        assert create_admin.main() == 1


class TestMigration:
    def test_saved_views_created_by_added_to_old_db(self, db):
        # Simulate a pre-auth DB: drop the column by recreating the table without it,
        # then run migrate and expect it back.
        from sqlalchemy import text
        from app import migrate
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE saved_views"))
            conn.execute(text(
                "CREATE TABLE saved_views (id INTEGER PRIMARY KEY, name VARCHAR(120), "
                "config TEXT, created_at DATETIME)"
            ))
            conn.commit()
        migrate.run(engine)
        cols = {c["name"] for c in inspect(engine).get_columns("saved_views")}
        assert "created_by" in cols
