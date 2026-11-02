from datetime import datetime,timedelta,timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db import get_db
from app.models import User
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
oauth=OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def create_token(user):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub":user.id,"exp":exp},settings.secret_key,algorithm="HS256")
def current_user(token:str=Depends(oauth),db:Session=Depends(get_db)):
    try: uid=jwt.decode(token,settings.secret_key,algorithms=["HS256"]).get("sub")
    except JWTError: raise HTTPException(status_code=401,detail="Invalid or expired session")
    user=db.get(User,uid)
    if not user or not user.is_active: raise HTTPException(status_code=401,detail="Account unavailable")
    return user
def require_roles(*roles):
    def check(user:User=Depends(current_user)):
        if user.role.value not in roles: raise HTTPException(status_code=403,detail="Insufficient permissions")
        return user
    return check
