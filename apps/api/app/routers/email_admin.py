"""Administrator APIs for inspecting and safely retrying email deliveries."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, NotificationEmailLog
from app.security import require_roles
from app.services.email_retry import _send

router = APIRouter()

def _row(item, include_body=False):
    result = {"id":item.id,"user_id":item.user_id,"recipient_email":item.recipient_email,
      "subject":item.subject,"category":item.category,"status":item.status,
      "error_message":item.error_message,"sent_at":item.sent_at,"created_at":item.created_at,
      "retry_count":item.retry_count,"next_retry_at":item.next_retry_at}
    if include_body: result["email_body"] = item.email_body
    return result

@router.get('/admin/email-delivery-logs', tags=['administration','email-delivery'])
def email_delivery_logs(q: str = '', status: str = 'all', category: str = 'all',
                        page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                        db: Session = Depends(get_db), _admin: User = Depends(require_roles('admin'))):
    query=db.query(NotificationEmailLog)
    if status!='all': query=query.filter(NotificationEmailLog.status==status)
    if category!='all': query=query.filter(NotificationEmailLog.category==category)
    if q.strip():
        like=f"%{q.strip()}%"
        query=query.filter(or_(NotificationEmailLog.recipient_email.ilike(like),NotificationEmailLog.subject.ilike(like),NotificationEmailLog.user_id.ilike(like)))
    total=query.count();rows=query.order_by(NotificationEmailLog.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items":[_row(x) for x in rows],"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

@router.get('/admin/email-delivery-logs/summary', tags=['administration','email-delivery'])
def email_delivery_summary(db: Session = Depends(get_db), _admin: User = Depends(require_roles('admin'))):
    rows=db.query(NotificationEmailLog.status,func.count(NotificationEmailLog.id)).group_by(NotificationEmailLog.status).all()
    counts={status:int(count) for status,count in rows}
    return {key:counts.get(key,0) for key in ('sent','failed','retrying','dead_letter','pending')}

@router.get('/admin/email-delivery-analytics', tags=['administration','email-delivery'])
def email_delivery_analytics(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                             _admin: User = Depends(require_roles('admin'))):
    since=datetime.utcnow()-timedelta(days=days)
    rows=db.query(NotificationEmailLog).filter(NotificationEmailLog.created_at>=since).all()
    counts={key:0 for key in ('sent','failed','retrying','dead_letter','pending')};categories={};daily={}
    for row in rows:
        counts[row.status]=counts.get(row.status,0)+1
        categories[row.category]=categories.get(row.category,0)+1
        day=row.created_at.date().isoformat();entry=daily.setdefault(day,{"date":day,"total":0,"sent":0,"failed":0,"retrying":0,"dead_letter":0,"pending":0})
        entry['total']+=1;entry[row.status]=entry.get(row.status,0)+1
    total=len(rows)
    return {"total":total,"sent":counts['sent'],"failed":counts['failed'],"retrying":counts['retrying'],
      "dead_letter":counts['dead_letter'],"pending":counts['pending'],
      "success_rate":round(counts['sent']*100/total,2) if total else 0,
      "category_breakdown":categories,"daily":[daily[k] for k in sorted(daily)]}

@router.get('/admin/email-delivery-logs/{log_id}', tags=['administration','email-delivery'])
def email_delivery_detail(log_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_roles('admin'))):
    item=db.get(NotificationEmailLog,log_id)
    if not item: raise HTTPException(404,'Email delivery record not found')
    return _row(item,include_body=True)

@router.post('/admin/email-delivery-logs/{log_id}/retry', tags=['administration','email-delivery'])
def retry_email_delivery(log_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_roles('admin'))):
    item=db.get(NotificationEmailLog,log_id)
    if not item: raise HTTPException(404,'Email delivery record not found')
    if item.status not in {'failed','dead_letter'}: raise HTTPException(409,'Only failed or dead-letter emails can be retried')
    if not item.email_body: raise HTTPException(409,'This delivery has no retained message body to retry')
    try: _send(item)
    except Exception as exc:
        item.retry_count=(item.retry_count or 0)+1;item.status='failed';item.error_message=str(exc)[:1000]
        item.next_retry_at=datetime.utcnow()+timedelta(minutes=1);db.commit()
        raise HTTPException(503,'Email provider did not accept the retry; delivery remains failed')
    item.status='sent';item.sent_at=datetime.utcnow();item.retry_count=(item.retry_count or 0)+1
    item.error_message=None;item.next_retry_at=None;item.retry_started_at=None;db.commit()
    return _row(item)

@router.post('/admin/email-delivery-logs/{log_id}/requeue', tags=['administration','email-delivery'])
def requeue_email_delivery(log_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_roles('admin'))):
    item=db.get(NotificationEmailLog,log_id)
    if not item: raise HTTPException(404,'Email delivery record not found')
    if item.status!='dead_letter': raise HTTPException(409,'Only dead-letter emails can be requeued')
    if not item.email_body: raise HTTPException(409,'This delivery has no retained message body to requeue')
    item.status='failed';item.retry_count=0;item.next_retry_at=datetime.utcnow();item.retry_started_at=None
    item.error_message=None;db.commit()
    return _row(item)
