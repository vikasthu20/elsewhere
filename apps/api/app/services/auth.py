"""Authentication response helpers; password/token primitives live in security.py."""
def normalize_email(email: str) -> str:
    return email.strip().lower()

def public_user(user):
    return {"id":user.id,"name":user.name,"email":user.email,
            "phone":user.phone,"role":user.role.value,
            "email_verified":user.email_verified}
