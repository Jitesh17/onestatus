"""CRUD functions. Routes stay thin; all DB work happens here."""
from sqlalchemy.orm import Session, selectinload
from . import models, schemas


# ---------- Projects ----------
def list_projects(db: Session):
    return db.query(models.Project).order_by(models.Project.id).all()


def create_project(db: Session, data: schemas.ProjectCreate):
    obj = models.Project(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- Tasks ----------
def list_tasks(db: Session, project_id: int | None = None):
    q = db.query(models.Task)
    if project_id is not None:
        q = q.filter(models.Task.project_id == project_id)
    return q.order_by(models.Task.id).all()


def create_task(db: Session, data: schemas.TaskCreate):
    obj = models.Task(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- Updates ----------
def list_updates(db: Session):
    return (
        db.query(models.Update)
        .options(
            selectinload(models.Update.blockers),
            selectinload(models.Update.risks),
            selectinload(models.Update.next_steps),
        )
        .order_by(models.Update.created_at.desc())
        .all()
    )


# ---------- World + name resolution (week 2 extraction) ----------
# A small fixed roster for now. Owners on updates are free text; this list grounds
# the extractor's name matching. Move to a table if people management is ever needed.
PEOPLE = ["Jitesh", "Neeraj", "Abhishake", "Shivam", "Tanaka-san", "Sato-san"]


def build_world(db: Session):
    """Assemble the extractor's world (projects, tasks, people) from the live DB."""
    projects = []
    for p in db.query(models.Project).order_by(models.Project.id).all():
        tasks = [t.title for t in p.tasks]
        projects.append({"name": p.name, "name_ja": p.name_ja, "tasks": tasks})
    return {"projects": projects, "people": PEOPLE}


def resolve_task_id(db: Session, project_name: str | None, task_title: str | None):
    """Map an extracted (project, task) name pair to a Task id, or None if unmatched.

    Tries exact title, then case-insensitive, then the Japanese title. Scopes to the
    named project when it is known so identically-titled tasks don't collide.
    """
    if not task_title:
        return None
    q = db.query(models.Task)
    if project_name and project_name != "unknown":
        proj = db.query(models.Project).filter(models.Project.name == project_name).first()
        if proj:
            q = q.filter(models.Task.project_id == proj.id)
    candidates = q.all()
    for t in candidates:
        if t.title == task_title:
            return t.id
    low = task_title.strip().lower()
    for t in candidates:
        if t.title.strip().lower() == low:
            return t.id
    for t in candidates:
        if t.title_ja and t.title_ja.strip() == task_title.strip():
            return t.id
    return None


def create_update(db: Session, data: schemas.UpdateCreate):
    """Create an update plus its nested blockers, risks, and next steps in one go."""
    obj = models.Update(
        task_id=data.task_id,
        author=data.author,
        language=data.language,
        raw_text=data.raw_text,
        source=data.source,
        confirmed=True,  # manual entry is confirmed by definition in week 1
    )
    obj.blockers = [models.Blocker(**b.model_dump()) for b in data.blockers]
    obj.risks = [models.Risk(**r.model_dump()) for r in data.risks]
    obj.next_steps = [models.NextStep(**n.model_dump()) for n in data.next_steps]
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- Dashboard metrics (week 5) ----------
# Fixed manager KPIs aggregated from the capture data. Semantics kept simple and stated:
#   - overall_progress: mean of Task.progress_pct (0 when there are no tasks)
#   - open_blockers: blockers recorded with status "open" (resolved ones excluded)
#   - open_risks: all risks (the schema has no resolved flag for risks)
# We do not reconcile a blocker's "current" state across multiple updates per task; counts
# reflect what was recorded. Move to a state model later if needed.
RECENT_LIMIT = 8
STATUS_KEYS = ["not_started", "in_progress", "blocked", "done"]


def _task_label(task):
    if not task:
        return None, None, None
    proj = task.project
    return task.title, (proj.name if proj else None), (proj.name_ja if proj else None)


_SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def dashboard_metrics(db: Session, config: dict | None = None):
    """Aggregate the fixed manager KPIs. With a week-6 `config`, focus/sort/limit the data:
      config = {project, status, severity, sort, limit} (None/absent = no filter).
    A project/status filter narrows which projects and tasks are counted; severity filters the
    blocker list; sort/limit reorder and cap the lists. `sections` is honored by the UI.
    """
    config = config or {}
    proj_f = config.get("project")
    status_f = config.get("status")
    sev_f = config.get("severity")
    sort = config.get("sort")
    limit = config.get("limit")

    projects = [p for p in db.query(models.Project).order_by(models.Project.id).all()
                if not proj_f or p.name == proj_f]
    proj_ids = {p.id for p in projects}
    tasks = [t for t in db.query(models.Task).all()
             if t.project_id in proj_ids and (not status_f or t.status.value == status_f)]
    task_ids = {t.id for t in tasks}
    # An update is in scope when its task is in scope (project/status filters apply via the task).
    updates = [u for u in list_updates(db) if u.task_id in task_ids]

    status_counts = {k: 0 for k in STATUS_KEYS}
    for t in tasks:
        status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1
    overall_progress = round(sum(t.progress_pct for t in tasks) / len(tasks)) if tasks else 0

    blockers_list, risks_list, by_severity = [], [], {"low": 0, "medium": 0, "high": 0}
    upcoming, recent = [], []
    for u in updates:
        title, pname, pname_ja = _task_label(u.task)
        for b in u.blockers:
            if b.status == "open" and (not sev_f or b.severity.value == sev_f):
                by_severity[b.severity.value] = by_severity.get(b.severity.value, 0) + 1
                blockers_list.append({
                    "description": b.description, "severity": b.severity.value, "owner": b.owner,
                    "task": title, "project": pname,
                })
        for r in u.risks:
            risks_list.append({
                "description": r.description, "impact": r.impact, "mitigation": r.mitigation,
                "owner": r.owner, "task": title, "project": pname,
            })
        for n in u.next_steps:
            upcoming.append({
                "description": n.description, "owner": n.owner,
                "due_date": n.due_date.isoformat() if n.due_date else None,
                "task": title, "project": pname,
            })
        recent.append({
            "id": u.id, "task": title, "project": pname, "author": u.author,
            "language": u.language, "source": u.source,
            "created_at": u.created_at, "snippet": (u.raw_text or "")[:140],
            "blocker_count": len(u.blockers), "risk_count": len(u.risks),
            "next_step_count": len(u.next_steps),
        })

    # Sorting (week 6). Defaults: blockers by severity, next steps by due date, activity newest-first.
    blockers_list.sort(key=lambda b: _SEV_RANK.get(b["severity"], 9))
    upcoming.sort(key=lambda s: (s["due_date"] is None, s["due_date"] or ""))

    per_project = []
    for p in projects:
        ptasks = [t for t in p.tasks if not status_f or t.status.value == status_f]
        open_blk = sum(
            1 for t in ptasks for u in t.updates for b in u.blockers
            if b.status == "open" and (not sev_f or b.severity.value == sev_f)
        )
        per_project.append({
            "id": p.id, "name": p.name, "name_ja": p.name_ja, "status": p.status.value,
            "owner": p.owner, "task_count": len(ptasks),
            "avg_progress": round(sum(t.progress_pct for t in ptasks) / len(ptasks)) if ptasks else 0,
            "open_blocker_count": open_blk,
            "done_task_count": sum(1 for t in ptasks if t.status.value == "done"),
        })
    if sort == "progress":
        per_project.sort(key=lambda p: p["avg_progress"], reverse=True)

    # limit caps the list lengths; default recent cap still applies.
    cap = limit if (isinstance(limit, int) and limit > 0) else None
    recent_cap = cap or RECENT_LIMIT

    return {
        "totals": {"projects": len(projects), "tasks": len(tasks), "updates": len(updates)},
        "task_status_counts": status_counts,
        "overall_progress": overall_progress,
        "open_blockers": len(blockers_list),
        "open_blockers_by_severity": by_severity,
        "open_risks": len(risks_list),
        "blockers_list": blockers_list[:cap] if cap else blockers_list,
        "risks_list": risks_list[:cap] if cap else risks_list,
        "recent_updates": recent[:recent_cap],
        "upcoming_next_steps": upcoming[:cap] if cap else upcoming[:RECENT_LIMIT],
        "per_project": per_project,
    }


# ---------- Saved views (week 6) ----------
import json as _json  # noqa: E402  (local use only)


def list_views(db: Session):
    return db.query(models.SavedView).order_by(models.SavedView.id).all()


def create_view(db: Session, name: str, config: dict):
    obj = models.SavedView(name=name, config=_json.dumps(config))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_view(db: Session, view_id: int) -> bool:
    obj = db.get(models.SavedView, view_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def view_to_dict(obj):
    """Decode a SavedView row into the SavedViewOut shape (config as a dict)."""
    return {"id": obj.id, "name": obj.name, "config": _json.loads(obj.config),
            "created_at": obj.created_at}
