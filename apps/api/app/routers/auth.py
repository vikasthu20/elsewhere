"""Authentication, account security and profile endpoints."""
from datetime import datetime, timedelta
import os, smtplib
from email.message import EmailMessage
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.models import User, OtpChallenge
from app.security import current_user, hash_password, verify_password
from app.core.config import settings
from app.services.auth import normalize_email, public_user
from app.services.operations import make_otp, hash_otp, verify_otp, otp_expiry, audit

router = APIRouter()

class EmailOnlyIn(BaseModel):
    email: EmailStr

class OtpConfirmIn(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")

class PasswordResetConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=10, max_length=128)

class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

class ProfileUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)

def _send_security_code(email: str, code: str, purpose: str):
    host=os.getenv("SMTP_HOST","").strip()
    sender=os.getenv("SMTP_FROM","").strip()
    if not host or not sender:
        raise HTTPException(503, "Email delivery is not configured. Configure SMTP_HOST and SMTP_FROM.")
    message=EmailMessage()
    message["Subject"] = "Your Elsewhere security code"
    message["From"] = sender
    message["To"] = email
    message.set_content(f"Your Elsewhere {purpose.replace('_',' ')} code is {code}. It expires in 5 minutes. If you did not request this, ignore this email.")
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT","587")), timeout=8) as server:
            if os.getenv("SMTP_STARTTLS","true").lower() in ("1","true","yes"):
                server.starttls()
            username=os.getenv("SMTP_USER","").strip()
            if username:
                server.login(username,os.getenv("SMTP_PASSWORD",""))
            server.send_message(message)
    except Exception:
        raise HTTPException(502, "Unable to deliver the security email. Please try again later.")

def _create_challenge(db: Session, destination: str, purpose: str):
    recent=db.query(OtpChallenge).filter(
        OtpChallenge.destination==destination,
        OtpChallenge.purpose==purpose,
        OtpChallenge.created_at >= datetime.utcnow()-timedelta(minutes=15)
    ).count()
    if recent >= 3:
        raise HTTPException(429, "Too many code requests. Try again in 15 minutes.")
    code=make_otp()
    challenge=OtpChallenge(destination=destination,purpose=purpose,
        code_hash=hash_otp(code, __import__("app.core.config",fromlist=["settings"]).settings.otp_secret),
        expires_at=otp_expiry(5))
    db.add(challenge)
    db.commit()
    if settings.otp_delivery_mode.strip().lower() == "console":
        return {"message": "Development verification code created. It expires in 5 minutes.",
                "development_code": code}
    try:
        _send_security_code(destination,code,purpose)
    except Exception:
        db.delete(challenge); db.commit()
        raise
    return {"message":"If the address is eligible, a security code has been sent. It expires in 5 minutes."}

def _consume_challenge(db: Session, destination: str, purpose: str, code: str):
    challenge=db.query(OtpChallenge).filter(
        OtpChallenge.destination==destination, OtpChallenge.purpose==purpose,
        OtpChallenge.consumed_at.is_(None)
    ).order_by(OtpChallenge.created_at.desc()).first()
    if not challenge or challenge.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired security code.")
    if challenge.attempts >= 5:
        raise HTTPException(429,"Too many incorrect attempts. Request a new code.")
    challenge.attempts += 1
    from app.core.config import settings
    if not verify_otp(code,challenge.code_hash,settings.otp_secret):
        db.commit()
        raise HTTPException(400,"Invalid or expired security code.")
    challenge.consumed_at=datetime.utcnow()
    db.commit()
    return challenge

from app.legacy_routes import register, login, me
router.add_api_route('/auth/register', register, methods=['POST'], status_code=201, tags=['authentication'])
router.add_api_route('/auth/login', login, methods=['POST'], tags=['authentication'])
router.add_api_route('/auth/me', me, methods=['GET'], tags=['authentication'])

@router.post("/auth/logout", tags=["authentication"])
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.auth_token_version += 1
    audit(db,user.id,"auth.sessions.revoked","user",user.id,{"scope":"all_sessions"})
    db.commit()
    return {"message":"All active sessions have been revoked. Sign in again to continue."}

@router.patch("/auth/me", tags=["authentication"])
def update_profile(data: ProfileUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name=data.name.strip()
    user.phone=data.phone.strip() if data.phone and data.phone.strip() else None
    db.commit(); db.refresh(user)
    return public_user(user)

@router.post("/auth/password/change", tags=["authentication"])
def change_password(data: PasswordChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password,user.password_hash):
        raise HTTPException(400,"Current password is incorrect.")
    if data.current_password == data.new_password:
        raise HTTPException(400,"Choose a password different from your current password.")
    user.password_hash=hash_password(data.new_password)
    user.auth_token_version += 1
    audit(db,user.id,"auth.password.changed","user",user.id,{"sessions_revoked":True})
    db.commit()
    return {"message":"Password updated. Please sign in again on your devices."}

@router.post("/auth/email-verification/request", tags=["authentication"])
def request_email_verification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified:
        return {"message":"Email address is already verified."}
    return _create_challenge(db,normalize_email(user.email),"verify_contact")

@router.post("/auth/email-verification/confirm", tags=["authentication"])
def confirm_email_verification(data: OtpConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _consume_challenge(db,normalize_email(user.email),"verify_contact",data.code)
    user.email_verified=True
    db.commit()
    return {"message":"Email address verified.","user":public_user(user)}

@router.post("/auth/password-reset/request", tags=["authentication"])
def request_password_reset(data: EmailOnlyIn, db: Session = Depends(get_db)):
    email=normalize_email(str(data.email))
    user=db.query(User).filter(func.lower(User.email)==email).first()
    # Keep response generic to avoid account enumeration.
    if user:
        _create_challenge(db,email,"password_reset")
    return {"message":"If the account exists and email delivery is configured, a reset code will be sent."}

@router.post("/auth/password-reset/confirm", tags=["authentication"])
def confirm_password_reset(data: PasswordResetConfirmIn, db: Session = Depends(get_db)):
    email=normalize_email(str(data.email))
    user=db.query(User).filter(func.lower(User.email)==email).first()
    if not user:
        raise HTTPException(400,"Invalid or expired security code.")
    _consume_challenge(db,email,"password_reset",data.code)
    user.password_hash=hash_password(data.new_password)
    user.auth_token_version += 1
    audit(db,user.id,"auth.password.reset","user",user.id,{"sessions_revoked":True})
    db.commit()
    return {"message":"Password reset complete. Sign in with your new password."}
