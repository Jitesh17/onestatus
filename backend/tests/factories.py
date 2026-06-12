"""Plain ORM factory helpers. Tests build exactly the rows they assert on, with
explicit control over created_at, severities, and the roster (seed_demo cannot
backdate deterministically because its history is relative to now)."""
import datetime as dt

from app import models

S = models.Status
SV = models.Severity


def make_project(db, name="Proj A", **kw):
    obj = models.Project(name=name, **kw)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def make_task(db, project, title="Task 1", status=S.in_progress, progress_pct=50,
              assignee=None, **kw):
    obj = models.Task(project_id=project.id, title=title, status=status,
                      progress_pct=progress_pct, assignee=assignee, **kw)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def make_update(db, task=None, created_at=None, status=None, progress_pct=None,
                blockers=(), risks=(), next_steps=(), **kw):
    """blockers: (description, severity, owner, status) tuples;
    risks: (description,) or (description, impact, mitigation, owner);
    next_steps: (description, owner, due_date)."""
    obj = models.Update(
        task_id=task.id if task else None,
        status=status, progress_pct=progress_pct,
        created_at=created_at or dt.datetime.utcnow(),
        **kw,
    )
    obj.blockers = [
        models.Blocker(description=b[0],
                       severity=b[1] if len(b) > 1 and b[1] else SV.medium,
                       owner=b[2] if len(b) > 2 else None,
                       status=b[3] if len(b) > 3 else "open")
        for b in blockers
    ]
    obj.risks = [
        models.Risk(description=r[0],
                    impact=r[1] if len(r) > 1 else None,
                    mitigation=r[2] if len(r) > 2 else None,
                    owner=r[3] if len(r) > 3 else None)
        for r in risks
    ]
    obj.next_steps = [
        models.NextStep(description=n[0],
                        owner=n[1] if len(n) > 1 else None,
                        due_date=n[2] if len(n) > 2 else None)
        for n in next_steps
    ]
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def make_person(db, name, team=None, department=None, name_ja=None):
    obj = models.Person(name=name, name_ja=name_ja, team=team, department=department)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def days_ago(n, hour=10):
    return (dt.datetime.utcnow() - dt.timedelta(days=n)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
