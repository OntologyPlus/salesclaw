"""认证 API"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, User, Role, Tenant
from core.response import unified_response
from middleware.auth import get_current_user
from services.auth_service import authenticate, create_tokens, refresh_tokens, change_password

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user, tenant = authenticate(db, req.username, req.password, req.tenant_code)
    role = db.query(Role).filter(Role.id == user.role_id).first() if user.role_id else None
    tokens = create_tokens(user, tenant, role)
    return unified_response({
        **tokens,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": role.code if role else None,
        }
    })


@router.post("/refresh")
async def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    tokens = refresh_tokens(db, req.refresh_token)
    return unified_response(tokens)


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    # Mock: 实际可清除服务端 session
    return unified_response({"logged_out": True})


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return unified_response({
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "tenant_id": user.tenant_id,
    })


@router.put("/password")
async def update_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, user, req.old_password, req.new_password)
    return unified_response({"changed": True})
