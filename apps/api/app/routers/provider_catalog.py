"""Provider profiles, package catalogue, and agency booking request APIs."""
import json
import re
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import (User, ProviderProfile, TourPackage, TourPackageRequest, Vehicle,
                        AuditLog, Notification)
from app.schemas import ProviderProfileIn
from app.security import current_user, require_roles
from app.services.operations import audit

router=APIRouter()

class PackageInput(BaseModel):
    title: str = Field(min_length=3,max_length=180)
    destination: str = Field(min_length=2,max_length=180)
    summary: str = Field(default='',max_length=500)
    description: str = Field(default='',max_length=12000)
    duration_days: int = Field(ge=1,le=60)
    price_per_person: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    currency: str = Field(default='INR',min_length=3,max_length=3)
    max_travellers: int = Field(default=10,ge=1,le=500)
    itinerary: list[dict] = Field(default_factory=list,max_length=100)
    inclusions: list[str] = Field(default_factory=list,max_length=100)
    exclusions: list[str] = Field(default_factory=list,max_length=100)
    image_url: str|None = Field(default=None,max_length=500)
    is_published: bool = False

def _decode(raw, fallback):
    try: return json.loads(raw or '')
    except (ValueError,TypeError): return fallback

def _package(item):
    return {"id":item.id,"slug":item.slug,"title":item.title,"destination":item.destination,
      "summary":item.summary,"description":item.description,"duration_days":item.duration_days,
      "price_per_person":float(item.price_per_person),"currency":item.currency,"max_travellers":item.max_travellers,
      "itinerary":_decode(item.itinerary_json,[]),"inclusions":_decode(item.inclusions,[]),
      "exclusions":_decode(item.exclusions,[]),"image_url":item.image_url,"is_published":item.is_published,
      "status":"published" if item.is_published else "draft"}

def _slug(title, item_id):
    base=re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')[:150] or 'tour'
    return f"{base}-{item_id[:8]}"

def _request(item,db):
    package=db.get(TourPackage,item.package_id); customer=db.get(User,item.customer_id)
    return {"id":item.id,"package_id":item.package_id,"package_title":package.title if package else "Tour package",
      "package_slug":package.slug if package else "","destination":package.destination if package else "",
      "customer_id":item.customer_id,"customer_name":customer.name if customer else "Traveller",
      "customer_email":customer.email if customer else "","provider_id":item.provider_id,
      "start_date":item.start_date.isoformat(),"travellers":item.travellers,"contact_phone":item.contact_phone,
      "message":item.message,"status":item.status,"provider_note":item.provider_note,
      "created_at":item.created_at.isoformat() if item.created_at else None}

@router.get('/providers/me/profile',tags=['providers'])
def get_provider_profile(db:Session=Depends(get_db),user:User=Depends(require_roles('owner','agency','admin'))):
    row=db.query(ProviderProfile).filter(ProviderProfile.user_id==user.id).first()
    profile=None if row is None else {"business_name":row.business_name,"description":row.description,
      "contact_phone":row.contact_phone,"website_url":row.website_url,"address":row.address,
      "service_areas":_decode(row.service_areas_json,[]),"pricing_notes":row.pricing_notes}
    vehicles=db.query(Vehicle).filter(Vehicle.owner_id==user.id)
    total=vehicles.count();verified=vehicles.filter(Vehicle.verified.is_(True)).count()
    pending=vehicles.filter(Vehicle.verified.is_(False)).count()
    starting=vehicles.filter(Vehicle.verified.is_(True),Vehicle.available.is_(True)).order_by(Vehicle.price_per_day).first()
    return {"profile":profile,"inventory":{"total":total,"verified":verified,"pending":pending,
      "starting_price_per_day":float(starting.price_per_day) if starting else None}}

@router.put('/providers/me/profile',tags=['providers'])
def save_provider_profile(data:ProviderProfileIn,db:Session=Depends(get_db),user:User=Depends(require_roles('owner','agency','admin'))):
    row=db.query(ProviderProfile).filter(ProviderProfile.user_id==user.id).first()
    if row is None:row=ProviderProfile(user_id=user.id);db.add(row)
    row.business_name=data.business_name.strip();row.description=data.description
    row.contact_phone=data.contact_phone;row.website_url=data.website_url;row.address=data.address
    row.service_areas_json=json.dumps([x.strip() for x in data.service_areas if x.strip()])
    row.pricing_notes=data.pricing_notes
    audit(db,user.id,'provider.profile.updated','provider_profile',row.id)
    db.commit()
    return {"saved":True}

@router.get('/providers/me/tour-packages',tags=['tour-packages'])
def provider_packages(db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    rows=db.query(TourPackage).filter(TourPackage.provider_id==user.id).order_by(TourPackage.updated_at.desc()).all()
    return [_package(x) for x in rows]

@router.post('/providers/me/tour-packages',status_code=201,tags=['tour-packages'])
def create_provider_package(data:PackageInput,db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    item=TourPackage(provider_id=user.id,title=data.title.strip(),destination=data.destination.strip(),summary=data.summary.strip(),
      description=data.description,duration_days=data.duration_days,price_per_person=data.price_per_person,
      currency=data.currency.upper(),max_travellers=data.max_travellers,itinerary_json=json.dumps(data.itinerary),
      inclusions=json.dumps(data.inclusions),exclusions=json.dumps(data.exclusions),image_url=data.image_url,
      is_published=data.is_published,status='published' if data.is_published else 'draft')
    db.add(item);db.flush();item.slug=_slug(item.title,item.id)
    audit(db,user.id,'tour_package.created','tour_package',item.id);db.commit();db.refresh(item)
    return _package(item)

@router.put('/providers/me/tour-packages/{package_id}',tags=['tour-packages'])
def update_provider_package(package_id:str,data:PackageInput,db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    item=db.query(TourPackage).filter(TourPackage.id==package_id,TourPackage.provider_id==user.id).first()
    if not item:raise HTTPException(404,'Tour package not found')
    for key,value in data.model_dump().items():
        if key=='itinerary':item.itinerary_json=json.dumps(value)
        elif key in ('inclusions','exclusions'):setattr(item,key,json.dumps(value))
        elif key=='is_published':item.is_published=value;item.status='published' if value else 'draft'
        else:setattr(item,key,value)
    audit(db,user.id,'tour_package.updated','tour_package',item.id);db.commit();db.refresh(item)
    return _package(item)

@router.delete('/providers/me/tour-packages/{package_id}',tags=['tour-packages'])
def delete_provider_package(package_id:str,db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    item=db.query(TourPackage).filter(TourPackage.id==package_id,TourPackage.provider_id==user.id).first()
    if not item:raise HTTPException(404,'Tour package not found')
    if db.query(TourPackageRequest).filter(TourPackageRequest.package_id==item.id).first():
        raise HTTPException(409,'A package with booking requests cannot be deleted; unpublish it instead')
    db.delete(item);db.commit();return {"id":package_id,"deleted":True}

@router.get('/tour-packages',tags=['tour-packages'])
def public_packages(q:str='',destination:str='',min_days:int=Query(0,ge=0),max_days:int=Query(60,ge=1,le=365),
                    max_price:Decimal|None=None,sort:str='newest',limit:int=Query(60,ge=1,le=100),
                    db:Session=Depends(get_db)):
    query=db.query(TourPackage).filter(TourPackage.is_published.is_(True))
    if q.strip():
        like=f"%{q.strip()}%";query=query.filter(or_(TourPackage.title.ilike(like),TourPackage.summary.ilike(like),TourPackage.description.ilike(like)))
    if destination.strip():query=query.filter(TourPackage.destination.ilike(f"%{destination.strip()}%"))
    query=query.filter(TourPackage.duration_days>=min_days,TourPackage.duration_days<=max_days)
    if max_price is not None:query=query.filter(TourPackage.price_per_person<=max_price)
    order={'newest':TourPackage.created_at.desc(),'price_asc':TourPackage.price_per_person.asc(),
      'price_desc':TourPackage.price_per_person.desc(),'duration_asc':TourPackage.duration_days.asc()}.get(sort)
    if order is None:raise HTTPException(422,'Invalid package sort order')
    return [_package(x) for x in query.order_by(order).limit(limit).all()]

@router.get('/tour-packages/{slug}',tags=['tour-packages'])
def public_package_detail(slug:str,db:Session=Depends(get_db)):
    item=db.query(TourPackage).filter(TourPackage.slug==slug,TourPackage.is_published.is_(True)).first()
    if not item:raise HTTPException(404,'Tour package not found')
    return _package(item)

@router.get('/tour-package-requests/mine',tags=['tour-package-requests'])
def customer_package_requests(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.query(TourPackageRequest).filter(TourPackageRequest.customer_id==user.id).order_by(TourPackageRequest.created_at.desc()).all()
    return [_request(row,db) for row in rows]

@router.patch('/tour-package-requests/{request_id}/cancel',tags=['tour-package-requests'])
def cancel_package_request(request_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.query(TourPackageRequest).filter(TourPackageRequest.id==request_id,TourPackageRequest.customer_id==user.id).first()
    if not item:raise HTTPException(404,'Tour package request not found')
    if item.status not in {'requested','reviewing'}:raise HTTPException(409,'This request can no longer be cancelled')
    item.status='cancelled';audit(db,user.id,'tour_package_request.cancelled','tour_package_request',item.id);db.commit()
    return _request(item,db)

@router.get('/providers/me/tour-package-requests',tags=['tour-package-requests'])
def provider_package_requests(status:str='',db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    query=db.query(TourPackageRequest).filter(TourPackageRequest.provider_id==user.id)
    if status:query=query.filter(TourPackageRequest.status==status)
    return [_request(row,db) for row in query.order_by(TourPackageRequest.created_at.desc()).all()]

@router.patch('/providers/me/tour-package-requests/{request_id}',tags=['tour-package-requests'])
def update_provider_package_request(request_id:str,data:dict,db:Session=Depends(get_db),user:User=Depends(require_roles('agency','owner','admin'))):
    item=db.query(TourPackageRequest).filter(TourPackageRequest.id==request_id,TourPackageRequest.provider_id==user.id).first()
    if not item:raise HTTPException(404,'Tour package request not found')
    status=data.get('status');note=str(data.get('provider_note') or '').strip()
    if status not in {'reviewing','confirmed','declined'}:raise HTTPException(422,'Invalid request status')
    if item.status not in {'requested','reviewing'}:raise HTTPException(409,'This request has already been decided')
    item.status=status;item.provider_note=note
    db.add(Notification(user_id=item.customer_id,title='Tour package request updated',
      body=f"Your request for {_request(item,db)['package_title']} is now {status}.",channel='in_app'))
    audit(db,user.id,'tour_package_request.updated','tour_package_request',item.id,{'status':status})
    db.commit();db.refresh(item)
    return _request(item,db)
