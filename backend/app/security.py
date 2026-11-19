import hashlib
import hmac
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import JWT_SECRET, JWT_HOURS, PSEUDONYM_SALT
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS)
    return jwt.encode({'sub': str(user.id), 'role': user.role, 'exp': exp}, JWT_SECRET, algorithm='HS256')


def pseudonymise(card_no: str) -> str:
    """Keyed hash (HMAC-SHA256) of a clinic card number. The card number itself is never stored."""
    norm = card_no.strip().upper()
    return hmac.new(PSEUDONYM_SALT.encode(), norm.encode(), hashlib.sha256).hexdigest()[:32]


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Please sign in.')
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=['HS256'])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Your session has expired. Please sign in again.')
    user = db.get(User, int(payload['sub']))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'This account is not active.')
    return user


def require(*roles):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'You do not have permission to do this.')
        return user
    return checker


ANY_ROLE = ('admin', 'records_officer', 'analyst')
