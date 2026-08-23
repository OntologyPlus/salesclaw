"""认证服务"""
from datetime import datetime
from sqlalchemy.orm import Session
from core.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from core.exceptions import UnauthorizedError, TokenExpiredError, ValidationError, NotFoundError
from database import User, Tenant, Role, SessionRecord


def authenticate(db: Session, username: str, password: str, tenant_code: str) -> tuple[User, Tenant]:
    """验证用户名密码 + 租户码"""
    # 1. 查租户
    tenant = db.query(Tenant).filter(Tenant.code == tenant_code, Tenant.is_active == 1).first()
    if not tenant:
        raise NotFoundError("租户不存在")
    # 2. 查用户
    user = db.query(User).filter(
        User.tenant_id == str(tenant.id),
        User.username == username,
        User.is_deleted == 0,
        User.is_active == 1,
    ).first()
    if not user:
        raise UnauthorizedError("用户名或密码错误")
    # 3. 验证密码
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("用户名或密码错误")
    # 4. 更新最后登录时间
    user.last_login_at = datetime.utcnow()
    db.commit()
    return user, tenant


def create_tokens(user: User, tenant: Tenant, role: Role) -> dict:
    """创建 access_token + refresh_token"""
    permissions = role.permissions if role else []
    role_code = role.code if role else "user"
    access_token = create_access_token(user.id, str(tenant.id), role_code, permissions)
    refresh_token = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600,
    }


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    """刷新 token"""
    import jwt
    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        raise UnauthorizedError("无效的 refresh_token")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Token 类型错误")

    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id, User.is_deleted == 0, User.is_active == 1).first()
    if not user:
        raise UnauthorizedError("用户不存在")

    tenant = db.query(Tenant).filter(Tenant.id == int(user.tenant_id)).first()
    if not tenant:
        raise NotFoundError("租户不存在")

    role = db.query(Role).filter(Role.id == user.role_id).first() if user.role_id else None
    return create_tokens(user, tenant, role)


def change_password(db: Session, user: User, old_password: str, new_password: str):
    """修改密码"""
    if not verify_password(old_password, user.password_hash):
        raise ValidationError("原密码错误")
    if len(new_password) < 6:
        raise ValidationError("新密码长度不能少于6位")
    user.password_hash = hash_password(new_password)
    db.commit()
