from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EditorialContent, User
from app.security import require_roles

router = APIRouter()
_FIELDS = {"title", "slug", "content_type", "summary", "body", "image_url",
           "destination_name", "is_featured", "is_published", "sort_order"}


def _serialize(row: EditorialContent) -> dict:
    return {key: getattr(row, key) for key in ("id", *_FIELDS)}


@router.get("/content", tags=["editorial"])
def list_published_content(content_type: str | None = None,
                           limit: int = Query(30, ge=1, le=100),
                           db: Session = Depends(get_db)):
    query = db.query(EditorialContent).filter(EditorialContent.is_published.is_(True))
    if content_type and content_type != "all":
        query = query.filter(EditorialContent.content_type == content_type)
    return [_serialize(row) for row in query.order_by(
        EditorialContent.sort_order, EditorialContent.created_at.desc()).limit(limit).all()]


@router.get("/content/{slug}", tags=["editorial"])
def get_published_content(slug: str, db: Session = Depends(get_db)):
    row = db.query(EditorialContent).filter_by(slug=slug, is_published=True).first()
    if not row:
        raise HTTPException(404, "Story not found")
    return _serialize(row)


@router.get("/admin/content", tags=["administration"])
def list_admin_content(q: str = "", content_type: str = "all", status: str = "all",
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    query = db.query(EditorialContent)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(EditorialContent.title.ilike(term), EditorialContent.summary.ilike(term)))
    if content_type != "all":
        query = query.filter(EditorialContent.content_type == content_type)
    if status == "published":
        query = query.filter(EditorialContent.is_published.is_(True))
    elif status == "draft":
        query = query.filter(EditorialContent.is_published.is_(False))
    total = query.count()
    rows = query.order_by(EditorialContent.sort_order, EditorialContent.updated_at.desc()).offset(
        (page - 1) * page_size).limit(page_size).all()
    return {"items": [_serialize(row) for row in rows], "total": total,
            "page": page, "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size)}


@router.post("/admin/content", status_code=201, tags=["administration"])
def create_content(data: dict, db: Session = Depends(get_db),
                   _admin: User = Depends(require_roles("admin"))):
    values = {key: value for key, value in data.items() if key in _FIELDS}
    for required in ("title", "slug"):
        if not isinstance(values.get(required), str) or not values[required].strip():
            raise HTTPException(422, f"{required} is required")
    if values.get("content_type", "guide") not in {"guide", "highlight", "collection"}:
        raise HTTPException(422, "Invalid content type")
    row = EditorialContent(**values)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Content slug already exists")
    db.refresh(row)
    return _serialize(row)


@router.patch("/admin/content/{content_id}", tags=["administration"])
def update_content(content_id: str, data: dict, db: Session = Depends(get_db),
                   _admin: User = Depends(require_roles("admin"))):
    row = db.get(EditorialContent, content_id)
    if not row:
        raise HTTPException(404, "Content not found")
    values = {key: value for key, value in data.items() if key in _FIELDS}
    if "content_type" in values and values["content_type"] not in {"guide", "highlight", "collection"}:
        raise HTTPException(422, "Invalid content type")
    for key, value in values.items():
        setattr(row, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Content slug already exists")
    db.refresh(row)
    return _serialize(row)
