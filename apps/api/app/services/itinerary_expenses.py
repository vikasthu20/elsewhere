"""Persist itinerary expenses and receipt metadata in JSON columns."""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException, UploadFile
from app.core.config import settings
from app.models import Itinerary, User

ALLOWED_RECEIPT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
MAX_RECEIPT_BYTES = 5 * 1024 * 1024


def _load_list(raw: str | None) -> list:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _load_map(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _owned(item: Itinerary | None, user: User) -> Itinerary:
    if item is None:
        raise HTTPException(404, "Itinerary not found")
    # Public draft itineraries have no owner. Never let the first caller claim
    # one by guessing its identifier; only the creator's authenticated session
    # can own and access persisted expenses and receipts.
    if not item.user_id or item.user_id != user.id:
        raise HTTPException(404, "Itinerary not found")
    return item


def serialize_expenses(item: Itinerary) -> list:
    receipts = _load_map(item.receipts_json)
    expenses = []
    for expense in _load_list(item.expenses_json):
        if not isinstance(expense, dict) or not expense.get("id"):
            continue
        expense = dict(expense)
        expense["receipts"] = receipts.get(expense["id"], [])
        expenses.append(expense)
    return expenses


def add_expense(item: Itinerary, payload: dict) -> list:
    amount = payload.get("amount")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise HTTPException(400, "Enter an amount greater than zero.")
    if amount <= 0:
        raise HTTPException(400, "Enter an amount greater than zero.")
    category = str(payload.get("category") or "other").strip().lower()[:40] or "other"
    expense = {
        "id": str(uuid.uuid4()),
        "date": str(payload.get("date") or datetime.utcnow().date().isoformat())[:10],
        "category": category,
        "amount": round(amount, 2),
        "note": str(payload.get("note") or "")[:500],
        "created_at": datetime.utcnow().isoformat(),
    }
    expenses = _load_list(item.expenses_json)
    expenses.append(expense)
    item.expenses_json = json.dumps(expenses)
    return serialize_expenses(item)


def remove_expense(item: Itinerary, expense_id: str) -> list:
    expenses = [row for row in _load_list(item.expenses_json) if row.get("id") != expense_id]
    if len(expenses) == len(_load_list(item.expenses_json)):
        raise HTTPException(404, "Expense not found")
    item.expenses_json = json.dumps(expenses)
    receipts = _load_map(item.receipts_json)
    receipts.pop(expense_id, None)
    item.receipts_json = json.dumps(receipts)
    return serialize_expenses(item)


def _receipt_dir(itinerary_id: str) -> Path:
    path = Path(settings.upload_dir) / "itinerary-receipts" / itinerary_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_receipt(item: Itinerary, expense_id: str, upload: UploadFile) -> dict:
    expenses = _load_list(item.expenses_json)
    if not any(row.get("id") == expense_id for row in expenses):
        raise HTTPException(404, "Expense not found")
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    suffix = ALLOWED_RECEIPT_TYPES.get(content_type)
    if not suffix:
        raise HTTPException(400, "Receipt must be a JPEG, PNG, WebP or PDF file.")
    data = upload.file.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(400, "Receipt must be 5 MB or smaller.")
    receipt_id = str(uuid.uuid4())
    filename = os.path.basename(upload.filename or f"receipt{suffix}")[:180] or f"receipt{suffix}"
    storage_name = f"{receipt_id}{suffix}"
    dest = _receipt_dir(item.id) / storage_name
    dest.write_bytes(data)
    record = {
        "id": receipt_id,
        "filename": filename,
        "mime_type": content_type,
        "size_bytes": len(data),
        "storage_key": str(dest),
        "created_at": datetime.utcnow().isoformat(),
    }
    receipts = _load_map(item.receipts_json)
    receipts.setdefault(expense_id, []).append(record)
    item.receipts_json = json.dumps(receipts)
    return record


def find_receipt(item: Itinerary, expense_id: str, receipt_id: str) -> dict:
    receipts = _load_map(item.receipts_json).get(expense_id) or []
    for row in receipts:
        if row.get("id") == receipt_id:
            return row
    raise HTTPException(404, "Receipt not found")


def delete_receipt(item: Itinerary, expense_id: str, receipt_id: str) -> None:
    receipts = _load_map(item.receipts_json)
    rows = receipts.get(expense_id) or []
    remaining = [row for row in rows if row.get("id") != receipt_id]
    if len(remaining) == len(rows):
        raise HTTPException(404, "Receipt not found")
    removed = next(row for row in rows if row.get("id") == receipt_id)
    receipts[expense_id] = remaining
    item.receipts_json = json.dumps(receipts)
    path = Path(removed.get("storage_key") or "")
    if path.exists():
        path.unlink()
