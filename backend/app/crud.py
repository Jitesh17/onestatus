"""CRUD functions. Routes stay thin; all DB work happens here."""
import datetime as dt

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
# Fallback roster for DBs seeded before the `people` table existed (report-scenarios
# sprint). When the table has rows, it is the source of truth for people AND teams.
PEOPLE = ["Jitesh", "Neeraj", "Abhishake", "Shivam", "Tanaka-san", "Sato-san"]


def people_roster(db: Session):
    """All Person rows, ordered. Empty list when the org has never been seeded."""
    return db.query(models.Person).order_by(models.Person.id).all()


def build_world(db: Session):
    """Assemble the extractor's world (projects, tasks, people, teams) from the live DB.

    `teams` is consumed only by the view interpreter; the extractor reads projects/people
    and ignores the extra key.
    """
    projects = []
    for p in db.query(models.Project).order_by(models.Project.id).all():
        tasks = [t.title for t in p.tasks]
        projects.append({"name": p.name, "name_ja": p.name_ja, "tasks": tasks})
    roster = people_roster(db)
    people = [p.name for p in roster] if roster else list(PEOPLE)
    teams, seen = [], set()
    for p in roster:
        if p.team and p.team not in seen:
            seen.add(p.team)
            teams.append({"name": p.team,
                          "members": [m.name for m in roster if m.team == p.team]})
    return {"projects": projects, "people": people, "teams": teams}


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
    """Create an update plus its nested blockers, risks, and next steps in one go.

    status/progress_pct are stored on the Update as a point-in-time snapshot (trend history)
    AND patched onto the matched Task (current state), when provided.
    """
    obj = models.Update(
        task_id=data.task_id,
        author=data.author,
        language=data.language,
        raw_text=data.raw_text,
        source=data.source,
        confirmed=True,  # manual entry is confirmed by definition in week 1
        status=data.status.value if data.status else None,
        progress_pct=data.progress_pct,
    )
    obj.blockers = [models.Blocker(**b.model_dump()) for b in data.blockers]
    obj.risks = [models.Risk(**r.model_dump()) for r in data.risks]
    obj.next_steps = [models.NextStep(**n.model_dump()) for n in data.next_steps]
    db.add(obj)
    if data.task_id is not None and (data.status is not None or data.progress_pct is not None):
        task = db.get(models.Task, data.task_id)
        if task:
            if data.status is not None:
                task.status = data.status
            if data.progress_pct is not None:
                task.progress_pct = data.progress_pct
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


def _effective_range(config: dict | None):
    """Resolve the config's date fields into (start, end) dates, either side None = unbounded.

    `days` (relative lookback ending today) wins over date_from/date_to. Bad ISO strings are
    treated as absent rather than erroring: the NL interpreter feeds these fields.
    """
    config = config or {}
    today = dt.date.today()
    days = config.get("days")
    if isinstance(days, int) and days > 0:
        # Cap at ~100 years: a huge lookback means "everything", and an unbounded
        # subtraction overflows datetime.date for absurd values.
        return today - dt.timedelta(days=min(days, 36_500) - 1), today
    start = end = None
    raw_from, raw_to = config.get("date_from"), config.get("date_to")
    try:
        start = dt.date.fromisoformat(str(raw_from)[:10]) if raw_from else None
    except ValueError:
        start = None
    try:
        end = dt.date.fromisoformat(str(raw_to)[:10]) if raw_to else None
    except ValueError:
        end = None
    return start, end


def _assignee_scope(db: Session, config: dict | None):
    """Predicate(task) for the config's team/person filters, or None when neither is set.

    Team resolves to the member-name set from the `people` table; matching against the
    free-text Task.assignee is case-insensitive. An unknown team yields an empty set
    (nothing matches), which is honest: the filter was asked for and found nothing.
    """
    config = config or {}
    team = config.get("team")
    person = config.get("person")
    if not team and not person:
        return None
    members = None
    if team:
        members = {p.name.lower() for p in people_roster(db)
                   if p.team and p.team.lower() == str(team).lower()}

    def in_scope(task):
        a = (task.assignee or "").lower()
        if person and a != str(person).lower():
            return False
        if members is not None and a not in members:
            return False
        return True

    return in_scope


def dashboard_metrics(db: Session, config: dict | None = None):
    """Aggregate the fixed manager KPIs. With a week-6 `config`, focus/sort/limit the data:
      config = {project, status, severity, team, person, sort, limit, days, date_from, date_to}
      (None/absent = no filter).
    A project/status filter narrows which projects and tasks are counted; team/person narrow
    tasks by assignee (and prune projects left with no in-scope tasks); severity filters the
    blocker list; sort/limit reorder and cap the lists. `sections` is honored by the UI.
    A date range scopes the EVENT lists (activity, blockers, risks, next steps) and the trend
    axis; task/project counts and progress stay whole-world because they describe current STATE,
    not events in the window.
    """
    config = config or {}
    proj_f = config.get("project")
    status_f = config.get("status")
    sev_f = config.get("severity")
    sort = config.get("sort")
    limit = config.get("limit")
    range_start, range_end = _effective_range(config)
    scope = _assignee_scope(db, config)

    projects = [p for p in db.query(models.Project).order_by(models.Project.id).all()
                if not proj_f or p.name == proj_f]
    proj_ids = {p.id for p in projects}
    tasks = [t for t in db.query(models.Task).all()
             if t.project_id in proj_ids and (not status_f or t.status.value == status_f)]
    if scope:
        tasks = [t for t in tasks if scope(t)]
        scoped_proj_ids = {t.project_id for t in tasks}
        projects = [p for p in projects if p.id in scoped_proj_ids]
    task_ids = {t.id for t in tasks}
    # An update is in scope when its task is in scope (project/status filters apply via the task).
    updates = [u for u in list_updates(db) if u.task_id in task_ids]
    if range_start or range_end:
        updates = [u for u in updates
                   if (not range_start or u.created_at.date() >= range_start)
                   and (not range_end or u.created_at.date() <= range_end)]

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
        ptasks = [t for t in p.tasks
                  if (not status_f or t.status.value == status_f) and (not scope or scope(t))]
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

    # Team and person rollups (report-scenarios sprint). Rows come from the org roster so
    # the report mirrors the org chart, not just whoever happens to hold a task right now.
    # Counting runs over the already-scoped `tasks` (and the range-scoped `updates` for the
    # owner-matched signals), so all the filters above apply here too.
    roster = people_roster(db)
    by_assignee: dict[str, list] = {}
    for t in tasks:
        by_assignee.setdefault((t.assignee or "").lower(), []).append(t)

    team_f, person_f = config.get("team"), config.get("person")
    per_team, seen_teams = [], set()
    for member in roster:
        if not member.team or member.team in seen_teams:
            continue
        if team_f and member.team.lower() != str(team_f).lower():
            continue
        seen_teams.add(member.team)
        team_members = [m for m in roster if m.team == member.team]
        ttasks = [t for m in team_members for t in by_assignee.get(m.name.lower(), [])]
        open_blk = sum(
            1 for t in ttasks for u in t.updates for b in u.blockers
            if b.status == "open" and (not sev_f or b.severity.value == sev_f)
        )
        per_team.append({
            "team": member.team, "department": member.department,
            "members": [m.name for m in team_members],
            "task_count": len(ttasks),
            "done_task_count": sum(1 for t in ttasks if t.status.value == "done"),
            "avg_progress": round(sum(t.progress_pct for t in ttasks) / len(ttasks)) if ttasks else 0,
            "open_blocker_count": open_blk,
        })

    # Every roster member appears even with zero tasks (a manager wants to see idle people);
    # assignees missing from the roster get a team-less row so no work disappears. A
    # team/person focus narrows the rows to that team's members / that one person.
    roster_names = {p.name.lower() for p in roster}
    person_rows = [(p.name, p.team) for p in roster
                   if (not team_f or (p.team or "").lower() == str(team_f).lower())
                   and (not person_f or p.name.lower() == str(person_f).lower())]
    unknown: dict[str, str] = {}
    for t in tasks:
        a = (t.assignee or "").lower()
        if a and a not in roster_names and a not in unknown:
            unknown[a] = t.assignee
    person_rows += [(name, None) for name in unknown.values()]

    per_person = []
    for name, team in person_rows:
        key = name.lower()
        own = by_assignee.get(key, [])
        # Blockers touching this person: open ones on their own tasks, plus any open blocker
        # they own elsewhere. Dedup by id since both paths can see the same row.
        blk_ids = {b.id for t in own for u in t.updates for b in u.blockers
                   if b.status == "open" and (not sev_f or b.severity.value == sev_f)}
        blk_ids |= {b.id for u in updates for b in u.blockers
                    if b.status == "open" and (b.owner or "").lower() == key
                    and (not sev_f or b.severity.value == sev_f)}
        per_person.append({
            "name": name, "team": team,
            "task_count": len(own),
            "done_task_count": sum(1 for t in own if t.status.value == "done"),
            "avg_progress": round(sum(t.progress_pct for t in own) / len(own)) if own else 0,
            "open_blocker_count": len(blk_ids),
            "next_step_count": sum(1 for u in updates for n in u.next_steps
                                   if (n.owner or "").lower() == key),
        })
    per_person.sort(key=lambda r: r["task_count"], reverse=True)

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
        "per_team": per_team,
        "per_person": per_person,
        "trends": trend_series(db, config),
    }


# ---------- Trend series (trends sprint) ----------
# Daily history derived from Update snapshots; the data volume is tiny, so this recomputes
# on every dashboard call rather than caching.
TREND_MAX_POINTS = 60


def trend_series(db: Session, config: dict | None = None):
    """Daily {progress, blockers} series for the dashboard charts.

    progress: per day, mean over in-scope tasks of the last-known Update.progress_pct snapshot
      on/before that day (carry-forward; 0 before a task's first snapshot). A task with no
      snapshots at all contributes its current Task.progress_pct as a flat line (legacy rows).
    blockers: per day, max(0, opens<=day - resolves<=day), where each blocker row is an open or
      resolve event dated by its update's created_at (no blocker identity tracking; documented).
    Respects the config's project/status/team/person focus and date range. Axis capped at ~TREND_MAX_POINTS
    by sampling; the final day is always included.
    """
    config = config or {}
    proj_f = config.get("project")
    status_f = config.get("status")
    range_start, range_end = _effective_range(config)
    scope = _assignee_scope(db, config)

    projects = [p for p in db.query(models.Project).order_by(models.Project.id).all()
                if not proj_f or p.name == proj_f]
    proj_ids = {p.id for p in projects}
    tasks = [t for t in db.query(models.Task).all()
             if t.project_id in proj_ids and (not status_f or t.status.value == status_f)
             and (not scope or scope(t))]
    task_ids = {t.id for t in tasks}
    # All history for the in-scope tasks: carry-forward needs snapshots from BEFORE the range
    # start, so the date range trims the axis below, not this list.
    updates = [u for u in list_updates(db) if u.task_id in task_ids]
    if not updates or not tasks:
        return {"progress": [], "blockers": []}

    today = dt.date.today()
    start = range_start or min(u.created_at.date() for u in updates)
    end = min(range_end or today, today)
    if start > end:
        return {"progress": [], "blockers": []}

    snaps: dict[int, list] = {}     # task_id -> [(date, pct)] oldest-first
    events: list = []               # (date, +1 open / -1 resolve)
    for u in updates:
        day = u.created_at.date()
        if u.progress_pct is not None and u.task_id is not None:
            snaps.setdefault(u.task_id, []).append((day, u.progress_pct))
        for b in u.blockers:
            if b.status == "open":
                events.append((day, 1))
            elif b.status == "resolved":
                events.append((day, -1))
    for s in snaps.values():
        s.sort()

    n_days = (end - start).days + 1
    step = max(1, -(-n_days // TREND_MAX_POINTS))  # ceil division
    axis = [start + dt.timedelta(days=i) for i in range(0, n_days, step)]
    if axis[-1] != end:
        axis.append(end)

    progress_pts, blocker_pts = [], []
    for day in axis:
        vals = []
        for t in tasks:
            s = snaps.get(t.id)
            if s:
                last = 0
                for d, pct in s:
                    if d <= day:
                        last = pct
                    else:
                        break
                vals.append(last)
            else:
                vals.append(t.progress_pct)
        progress_pts.append({"date": day.isoformat(),
                             "value": round(sum(vals) / len(vals)) if vals else 0})
        open_n = sum(delta for d, delta in events if d <= day)
        blocker_pts.append({"date": day.isoformat(), "value": max(0, open_n)})
    return {"progress": progress_pts, "blockers": blocker_pts}


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
