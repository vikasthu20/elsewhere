import json
import math
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session
from app.db import get_db
from app.legacy_routes import create_itinerary, my_itineraries
from app.models import Itinerary, User
from app.security import current_user
from app.services import itinerary_expenses as expenses

router = APIRouter()
router.add_api_route('/itineraries', create_itinerary, methods=['POST'], status_code=201, tags=['itineraries'])
router.add_api_route('/itineraries/mine', my_itineraries, methods=['GET'], tags=['itineraries'])


@router.patch('/itineraries/{itinerary_id}/budget', tags=['itineraries'])
def update_itinerary_budget(itinerary_id: str, data: dict, db: Session = Depends(get_db),
                            user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    allowed = {"currency", "accommodation", "food", "transport", "activities", "other",
               "notes", "alert_threshold"}
    budget = {key: value for key, value in data.items() if key in allowed}
    currency = budget.get("currency", "INR")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise HTTPException(422, "Currency must be a three-letter code")
    budget["currency"] = currency.upper()
    for key in ("accommodation", "food", "transport", "activities", "other"):
        try:
            value = float(budget.get(key, 0))
        except (TypeError, ValueError):
            raise HTTPException(422, f"{key} must be a non-negative amount")
        if not math.isfinite(value) or value < 0:
            raise HTTPException(422, f"{key} must be a non-negative amount")
        budget[key] = round(value, 2)
    notes = budget.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise HTTPException(422, "Budget notes must be 2000 characters or fewer")
    budget["notes"] = notes
    try:
        threshold = int(budget.get("alert_threshold", 80))
    except (TypeError, ValueError):
        raise HTTPException(422, "Alert threshold must be between 1 and 100")
    if threshold < 1 or threshold > 100:
        raise HTTPException(422, "Alert threshold must be between 1 and 100")
    budget["alert_threshold"] = threshold
    item.budget_json = json.dumps(budget)
    db.commit()
    return {"budget": budget}


def _itinerary(itinerary_id: str, db: Session, user: User) -> Itinerary:
    return expenses._owned(db.get(Itinerary, itinerary_id), user)


@router.get('/itineraries/{itinerary_id}/expenses', tags=['itineraries'])
def list_itinerary_expenses(itinerary_id: str, db: Session = Depends(get_db),
                            user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    return {"expenses": expenses.serialize_expenses(item)}


@router.post('/itineraries/{itinerary_id}/expenses', status_code=201, tags=['itineraries'])
def create_itinerary_expense(itinerary_id: str, data: dict, db: Session = Depends(get_db),
                             user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    result = expenses.add_expense(item, data or {})
    db.commit()
    return {"expenses": result}


@router.delete('/itineraries/{itinerary_id}/expenses/{expense_id}', tags=['itineraries'])
def delete_itinerary_expense(itinerary_id: str, expense_id: str, db: Session = Depends(get_db),
                             user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    result = expenses.remove_expense(item, expense_id)
    db.commit()
    return {"expenses": result}


@router.post('/itineraries/{itinerary_id}/expenses/{expense_id}/receipts', status_code=201, tags=['itineraries'])
def upload_itinerary_expense_receipt(itinerary_id: str, expense_id: str, file: UploadFile = File(...),
                                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    record = expenses.store_receipt(item, expense_id, file)
    db.commit()
    return record


def _receipt_file(itinerary_id: str, expense_id: str, receipt_id: str, db: Session, user: User):
    item = _itinerary(itinerary_id, db, user)
    record = expenses.find_receipt(item, expense_id, receipt_id)
    path = Path(record.get("storage_key") or "")
    if not path.exists():
        raise HTTPException(404, "Receipt file is no longer available")
    return record, path


@router.get('/itineraries/{itinerary_id}/expenses/{expense_id}/receipts/{receipt_id}', tags=['itineraries'])
def download_itinerary_expense_receipt(itinerary_id: str, expense_id: str, receipt_id: str,
                                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    record, path = _receipt_file(itinerary_id, expense_id, receipt_id, db, user)
    return FileResponse(path, media_type=record.get("mime_type") or "application/octet-stream",
                        filename=record.get("filename") or path.name)


@router.get('/itineraries/{itinerary_id}/expenses/{expense_id}/receipts/{receipt_id}/preview', tags=['itineraries'])
def preview_itinerary_expense_receipt(itinerary_id: str, expense_id: str, receipt_id: str,
                                      db: Session = Depends(get_db), user: User = Depends(current_user)):
    record, path = _receipt_file(itinerary_id, expense_id, receipt_id, db, user)
    return FileResponse(path, media_type=record.get("mime_type") or "application/octet-stream")


@router.delete('/itineraries/{itinerary_id}/expenses/{expense_id}/receipts/{receipt_id}', tags=['itineraries'])
def delete_itinerary_expense_receipt(itinerary_id: str, expense_id: str, receipt_id: str,
                                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = _itinerary(itinerary_id, db, user)
    expenses.delete_receipt(item, expense_id, receipt_id)
    db.commit()
    return {"ok": True}
