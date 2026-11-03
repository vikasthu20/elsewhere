"""Administrative workspace APIs used by the web console."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, Role, Destination, Vehicle, Booking, PaymentRecord, AuditLog
from app.security import require_roles

router = APIRouter()

def _page(query, page: int, page_size: int):
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total, max(1, (total + page_size - 1) // page_size)

def _audit(db, actor, action, kind, resource, details):
    db.add(AuditLog(actor_id=actor.id, action=action, resource_type=kind,
                    resource_id=resource, details_json=__import__('json').dumps(details, default=str)))

@router.get('/admin/destinations', tags=['administration'])
def admin_destinations(q: str = '', status: str = 'all', page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                       admin: User = Depends(require_roles('admin', 'staff'))):
    query = db.query(Destination)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Destination.name.ilike(like), Destination.region.ilike(like), Destination.category.ilike(like)))
    if status == 'published': query = query.filter(Destination.is_published.is_(True))
    elif status == 'draft': query = query.filter(Destination.is_published.is_(False))
    rows, total, pages = _page(query.order_by(Destination.name), page, page_size)
    items = [{"id": x.id, "name": x.name, "region": x.region, "category": x.category,
              "description": x.description, "image_url": x.image_url, "latitude": x.latitude,
              "longitude": x.longitude, "is_published": x.is_published} for x in rows]
    return {"items": items, "total": total, "page": page, "pages": pages}

@router.patch('/admin/destinations/{destination_id}', tags=['administration'])
def update_admin_destination(destination_id: str, data: dict, db: Session = Depends(get_db),
                             admin: User = Depends(require_roles('admin', 'staff'))):
    item = db.get(Destination, destination_id)
    if not item: raise HTTPException(404, 'Destination not found')
    allowed = {'name','region','category','description','image_url','latitude','longitude','is_published'}
    for key, value in data.items():
        if key in allowed: setattr(item, key, value)
    _audit(db, admin, 'destination.updated', 'destination', item.id, {k:v for k,v in data.items() if k in allowed})
    db.commit()
    return {"id": item.id, "is_published": item.is_published}

@router.get('/admin/bookings', tags=['administration'])
def admin_bookings(q: str = '', status: str = 'all', page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                   admin: User = Depends(require_roles('admin', 'staff'))):
    query = db.query(Booking, User, Vehicle).join(User, Booking.customer_id == User.id).join(Vehicle, Booking.vehicle_id == Vehicle.id)
    if status != 'all': query = query.filter(Booking.status == status)
    if q.strip():
        like=f"%{q.strip()}%"
        query=query.filter(or_(Booking.id.ilike(like),User.name.ilike(like),User.email.ilike(like),Vehicle.title.ilike(like),Vehicle.city.ilike(like)))
    total=query.count(); rows=query.order_by(Booking.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    items=[]
    for b,u,v in rows:
        payment=db.query(PaymentRecord).filter(PaymentRecord.booking_id==b.id).order_by(PaymentRecord.id.desc()).first()
        items.append({"id":b.id,"status":b.status,"start_date":b.start_date.isoformat(),"end_date":b.end_date.isoformat(),
          "pickup_location":b.pickup_location,"total_amount":float(b.total_amount),"vehicle_title":v.title,"vehicle_city":v.city,
          "customer_name":u.name,"customer_email":u.email,"payment_status":payment.status if payment else 'unpaid',
          "payment_provider":payment.provider if payment else None})
    return {"items":items,"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

@router.patch('/admin/bookings/{booking_id}', tags=['administration'])
def update_admin_booking(booking_id: str, data: dict, db: Session = Depends(get_db),
                         admin: User = Depends(require_roles('admin','staff'))):
    booking=db.get(Booking,booking_id)
    if not booking: raise HTTPException(404,'Booking not found')
    status=data.get('status'); note=str(data.get('decision_note') or '').strip()
    if status not in {'confirmed','rejected','cancelled','completed'}: raise HTTPException(422,'Invalid booking status')
    if len(note)<5: raise HTTPException(422,'Decision note must contain at least 5 characters')
    if booking.status not in {'requested','confirmed'}: raise HTTPException(409,'Terminal bookings cannot be changed')
    before=booking.status; booking.status=status
    _audit(db,admin,'booking.admin_status_changed','booking',booking.id,{'from':before,'to':status,'note':note})
    db.commit()
    return {'id':booking.id,'status':booking.status}

@router.get('/admin/vehicles', tags=['administration'])
def admin_vehicles(q: str = '', status: str = 'all', page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                   admin: User = Depends(require_roles('admin','staff'))):
    query=db.query(Vehicle,User).join(User,Vehicle.owner_id==User.id)
    if status=='pending':query=query.filter(Vehicle.verified.is_(False))
    elif status=='verified':query=query.filter(Vehicle.verified.is_(True),Vehicle.available.is_(True))
    elif status=='suspended':query=query.filter(Vehicle.verified.is_(True),Vehicle.available.is_(False))
    if q.strip():
        like=f"%{q.strip()}%";query=query.filter(or_(Vehicle.title.ilike(like),Vehicle.make_model.ilike(like),Vehicle.city.ilike(like)))
    total=query.count();rows=query.order_by(Vehicle.title).offset((page-1)*page_size).limit(page_size).all()
    items=[{"id":v.id,"title":v.title,"category":v.category,"make_model":v.make_model,"seats":v.seats,
       "price_per_day":float(v.price_per_day),"city":v.city,"description":v.description,"image_url":v.image_url,
       "verified":v.verified,"available":v.available,"owner_name":u.name,"owner_email":u.email} for v,u in rows]
    return {"items":items,"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

@router.patch('/admin/vehicles/{vehicle_id}', tags=['administration'])
def update_admin_vehicle(vehicle_id: str, data: dict, db: Session = Depends(get_db),
                         admin: User = Depends(require_roles('admin','staff'))):
    vehicle=db.get(Vehicle,vehicle_id)
    if not vehicle: raise HTTPException(404,'Vehicle not found')
    note=str(data.get('decision_note') or '').strip()
    if len(note)<5: raise HTTPException(422,'Decision note must contain at least 5 characters')
    for key in ('verified','available'):
        if key in data:
            if not isinstance(data[key],bool): raise HTTPException(422,f'{key} must be boolean')
            setattr(vehicle,key,data[key])
    _audit(db,admin,'vehicle.admin_status_changed','vehicle',vehicle.id,{'verified':vehicle.verified,'available':vehicle.available,'note':note})
    db.commit()
    return {'id':vehicle.id,'verified':vehicle.verified,'available':vehicle.available}

@router.get('/admin/users', tags=['administration'])
def admin_users(q: str = '', role: str = 'all', status: str = 'all', page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                admin: User = Depends(require_roles('admin','staff'))):
    query=db.query(User)
    if q.strip():
        like=f"%{q.strip()}%";query=query.filter(or_(User.name.ilike(like),User.email.ilike(like),User.phone.ilike(like)))
    if role!='all':
        try: query=query.filter(User.role==Role(role))
        except ValueError: raise HTTPException(422,'Invalid role filter')
    if status=='active':query=query.filter(User.is_active.is_(True))
    elif status=='inactive':query=query.filter(User.is_active.is_(False))
    total=query.count();rows=query.order_by(User.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    items=[{"id":u.id,"name":u.name,"email":u.email,"phone":u.phone,"role":u.role.value,
            "is_active":u.is_active,"created_at":u.created_at.isoformat() if u.created_at else None} for u in rows]
    return {"items":items,"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

@router.patch('/admin/users/{user_id}', tags=['administration'])
def update_admin_user(user_id: str, data: dict, db: Session = Depends(get_db),
                      admin: User = Depends(require_roles('admin'))):
    user=db.get(User,user_id)
    if not user: raise HTTPException(404,'User not found')
    if user.id==admin.id and (data.get('is_active') is False or data.get('role') not in (None,'admin')):
        raise HTTPException(409,'You cannot deactivate or demote your own administrator account')
    if 'role' in data:
        try:user.role=Role(data['role'])
        except ValueError:raise HTTPException(422,'Invalid role')
    if 'is_active' in data:
        if not isinstance(data['is_active'],bool):raise HTTPException(422,'is_active must be boolean')
        user.is_active=data['is_active']
    _audit(db,admin,'user.admin_updated','user',user.id,{'role':user.role.value,'is_active':user.is_active})
    db.commit()
    return {'id':user.id,'role':user.role.value,'is_active':user.is_active}

@router.get('/admin/analytics/overview', tags=['administration'])
def admin_analytics_overview(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                             admin: User = Depends(require_roles('admin','staff'))):
    since=datetime.utcnow()-timedelta(days=days)
    bookings=db.query(Booking).filter(Booking.created_at>=since).all()
    statuses={}
    for booking in bookings:statuses[booking.status]=statuses.get(booking.status,0)+1
    payments=db.query(PaymentRecord).filter(PaymentRecord.status=='paid',PaymentRecord.created_at>=since).all()
    paid_ids={p.booking_id for p in payments}; paid_revenue=sum(float(p.amount) for p in payments)
    new_users=db.query(User).filter(User.created_at>=since,User.role==Role.customer).count()
    active_vehicles=db.query(Vehicle).filter(Vehicle.verified.is_(True),Vehicle.available.is_(True)).count()
    top_rows=db.query(Vehicle,func.count(Booking.id)).join(Booking,Booking.vehicle_id==Vehicle.id).filter(Booking.created_at>=since).group_by(Vehicle.id).order_by(func.count(Booking.id).desc()).limit(10).all()
    return {'bookings':len(bookings),'booking_status':statuses,'paid_revenue':paid_revenue,'captured_payments':len(payments),
      'new_users':new_users,'active_vehicles':active_vehicles,'total_users':db.query(User).count(),
      'top_vehicles':[{'id':v.id,'title':v.title,'city':v.city,'booking_count':count,
        'paid_revenue':sum(float(p.amount) for p in payments if p.booking_id in {b.id for b in bookings if b.vehicle_id==v.id})} for v,count in top_rows]}
