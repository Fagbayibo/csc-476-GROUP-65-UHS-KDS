from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..security import current_user, make_token, verify_password, hash_password, require

router = APIRouter(prefix='/api', tags=['auth'])


class Login(BaseModel):
    username: str
    password: str


def public(u: User):
    return {'id': u.id, 'username': u.username, 'full_name': u.full_name, 'email': u.email, 'role': u.role,
            'is_active': u.is_active}


@router.post('/auth/login')
def login(body: Login, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username.strip().lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, 'Incorrect username or password.')
    if not u.is_active:
        raise HTTPException(401, 'This account has been deactivated.')
    return {'token': make_token(u), 'user': public(u)}


@router.get('/auth/me')
def me(user: User = Depends(current_user)):
    return public(user)


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    full_name: str = Field(min_length=2)
    email: str | None = None
    password: str = Field(min_length=8)
    role: str


class PatchUser(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


ROLES = ('admin', 'records_officer', 'analyst')


@router.get('/users')
def list_users(db: Session = Depends(get_db), _=Depends(require('admin'))):
    return [public(u) for u in db.query(User).order_by(User.full_name).all()]


@router.post('/users', status_code=201)
def create_user(body: NewUser, db: Session = Depends(get_db), _=Depends(require('admin'))):
    if body.role not in ROLES:
        raise HTTPException(400, f'Role must be one of: {", ".join(ROLES)}.')
    uname = body.username.strip().lower()
    if db.query(User).filter(User.username == uname).first():
        raise HTTPException(409, 'That username is already taken.')
    u = User(username=uname, full_name=body.full_name.strip(), email=body.email, role=body.role,
             password_hash=hash_password(body.password))
    db.add(u); db.commit()
    return public(u)


@router.patch('/users/{uid}')
def patch_user(uid: int, body: PatchUser, db: Session = Depends(get_db), me_: User = Depends(require('admin'))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, 'User not found.')
    if uid == me_.id and (body.is_active is False or (body.role and body.role != 'admin')):
        raise HTTPException(400, 'You cannot deactivate or demote your own account.')
    if body.role:
        if body.role not in ROLES:
            raise HTTPException(400, 'Unknown role.')
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    return public(u)
