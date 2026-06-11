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
