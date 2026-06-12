"""API tests for the core CRUD surface: health, projects, tasks, updates, saved views."""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_project_round_trip(client):
    r = client.post("/projects", json={"name": "Website Redesign",
                                       "name_ja": "ウェブサイト刷新", "owner": "Alex"})
    assert r.status_code in (200, 201)
    pid = r.json()["id"]
    listed = client.get("/projects").json()
    assert [p["id"] for p in listed] == [pid]
    assert listed[0]["name_ja"] == "ウェブサイト刷新"


def test_task_round_trip_and_project_filter(client):
    p1 = client.post("/projects", json={"name": "P1"}).json()
    p2 = client.post("/projects", json={"name": "P2"}).json()
    t1 = client.post("/tasks", json={"project_id": p1["id"], "title": "T1"}).json()
    client.post("/tasks", json={"project_id": p2["id"], "title": "T2"})
    only_p1 = client.get(f"/tasks?project_id={p1['id']}").json()
    assert [t["id"] for t in only_p1] == [t1["id"]]
    assert len(client.get("/tasks").json()) == 2


def test_update_with_nested_items(client):
    p = client.post("/projects", json={"name": "P"}).json()
    t = client.post("/tasks", json={"project_id": p["id"], "title": "T"}).json()
    r = client.post("/updates", json={
        "task_id": t["id"], "author": "Sam", "raw_text": "stuck on license",
        "blockers": [{"description": "License expired", "severity": "high"}],
        "risks": [{"description": "Slip risk", "impact": "high"}],
        "next_steps": [{"description": "Renew license", "owner": "Sam",
                        "due_date": "2026-06-20"}],
    })
    assert r.status_code in (200, 201)
    body = r.json()
    assert body["blockers"][0]["severity"] == "high"
    assert body["risks"][0]["description"] == "Slip risk"
    assert body["next_steps"][0]["due_date"] == "2026-06-20"
    listed = client.get("/updates").json()
    assert len(listed) == 1 and len(listed[0]["blockers"]) == 1


def test_update_snapshot_patches_task(client):
    p = client.post("/projects", json={"name": "P"}).json()
    t = client.post("/tasks", json={"project_id": p["id"], "title": "T",
                                    "status": "in_progress", "progress_pct": 10}).json()
    client.post("/updates", json={"task_id": t["id"], "status": "blocked",
                                  "progress_pct": 40})
    task = client.get("/tasks").json()[0]
    assert task["status"] == "blocked" and task["progress_pct"] == 40


def test_update_without_snapshot_leaves_task(client):
    p = client.post("/projects", json={"name": "P"}).json()
    t = client.post("/tasks", json={"project_id": p["id"], "title": "T",
                                    "status": "in_progress", "progress_pct": 10}).json()
    client.post("/updates", json={"task_id": t["id"], "raw_text": "no numbers today"})
    task = client.get("/tasks").json()[0]
    assert task["status"] == "in_progress" and task["progress_pct"] == 10


def test_views_crud(client):
    r = client.post("/views", json={"name": "Blocked in Website",
                                    "config": {"project": "Website", "status": "blocked"}})
    assert r.status_code == 201
    vid = r.json()["id"]
    listed = client.get("/views").json()
    assert len(listed) == 1
    assert listed[0]["config"]["status"] == "blocked"
    assert client.delete(f"/views/{vid}").status_code == 204
    assert client.get("/views").json() == []
    assert client.delete(f"/views/{vid}").status_code == 404
