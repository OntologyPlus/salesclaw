"""合作伙伴（CSO）管理服务（v2.2 Phase 2）

对应《医药代表管理办法》第 8 条 CSO 委托管理：
- 持有人可委托 CSO 进行医药代表管理，但需签订管理协议 + 授权书
- CSO 4 项禁止行为（第 12 条）通过违规规则引擎校验
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ValidationError
from database import (
    PartnerOrganization, ManagementAgreement, AuthorizationLetter,
)
from services.compliance_service import append_compliance_audit_log

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# PartnerOrganization CRUD
# ──────────────────────────────────────────────

def list_organizations(db: Session, tenant_id: str, status: str = None,
                       page: int = 1, page_size: int = 20) -> dict:
    q = db.query(PartnerOrganization).filter(
        PartnerOrganization.tenant_id == tenant_id,
        PartnerOrganization.is_deleted == 0,
    )
    if status:
        q = q.filter(PartnerOrganization.status == status)
    total = q.count()
    items = q.order_by(PartnerOrganization.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_org(o) for o in items],
        "total": total, "page": page, "page_size": page_size,
    }


def get_organization(db: Session, tenant_id: str, org_id: int) -> dict:
    o = _get_org_or_raise(db, tenant_id, org_id)
    return _serialize_org(o)


def create_organization(db: Session, tenant_id: str, user_id: int, user_role: str, data: dict) -> dict:
    if not data.get("name"):
        raise ValidationError("name 不能为空")
    org = PartnerOrganization(
        tenant_id=tenant_id,
        name=data["name"],
        org_code=data.get("org_code"),
        org_type=data.get("org_type", "cso"),
        legal_person=data.get("legal_person"),
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
        contact_email=data.get("contact_email"),
        address=data.get("address"),
        business_license_url=data.get("business_license_url"),
        medical_license_url=data.get("medical_license_url"),
        status="pending",
        credit_score=100,
    )
    db.add(org)
    db.flush()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="partner_org.create",
        target="partner_organization", target_id=org.id,
        detail={"name": org.name, "org_code": org.org_code},
    )
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


def update_organization(db: Session, tenant_id: str, org_id: int,
                       user_id: int, user_role: str, data: dict) -> dict:
    o = _get_org_or_raise(db, tenant_id, org_id)
    for field in [
        "name", "org_code", "org_type", "legal_person",
        "contact_name", "contact_phone", "contact_email", "address",
        "business_license_url", "medical_license_url", "status",
        "credit_score", "is_blacklisted",
    ]:
        if field in data and data[field] is not None:
            setattr(o, field, data[field])
    if data.get("status") == "active" and not o.activated_at:
        o.activated_at = datetime.utcnow()
    if data.get("status") == "terminated" and not o.terminated_at:
        o.terminated_at = datetime.utcnow()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="partner_org.update",
        target="partner_organization", target_id=o.id,
        detail={"updated_fields": list(data.keys())},
    )
    db.commit()
    db.refresh(o)
    return _serialize_org(o)


def delete_organization(db: Session, tenant_id: str, org_id: int,
                        user_id: int, user_role: str) -> None:
    o = _get_org_or_raise(db, tenant_id, org_id)
    o.is_deleted = 1
    o.deleted_at = datetime.utcnow()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="partner_org.delete",
        target="partner_organization", target_id=o.id,
        detail={},
    )
    db.commit()


# ──────────────────────────────────────────────
# ManagementAgreement CRUD
# ──────────────────────────────────────────────

def list_agreements(db: Session, tenant_id: str, partner_org_id: int = None,
                    status: str = None, page: int = 1, page_size: int = 20) -> dict:
    q = db.query(ManagementAgreement).filter(
        ManagementAgreement.tenant_id == tenant_id,
        ManagementAgreement.is_deleted == 0,
    )
    if partner_org_id:
        q = q.filter(ManagementAgreement.partner_org_id == partner_org_id)
    if status:
        q = q.filter(ManagementAgreement.status == status)
    total = q.count()
    items = q.order_by(ManagementAgreement.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_agreement(g) for g in items],
        "total": total, "page": page, "page_size": page_size,
    }


def get_agreement(db: Session, tenant_id: str, agreement_id: int) -> dict:
    g = _get_agreement_or_raise(db, tenant_id, agreement_id)
    return _serialize_agreement(g)


def create_agreement(db: Session, tenant_id: str, user_id: int, user_role: str, data: dict) -> dict:
    if not data.get("partner_org_id"):
        raise ValidationError("partner_org_id 不能为空")
    g = ManagementAgreement(
        tenant_id=tenant_id,
        partner_org_id=data["partner_org_id"],
        agreement_no=data.get("agreement_no"),
        title=data.get("title"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        authorized_regions=data.get("authorized_regions") or [],
        authorized_drug_categories=data.get("authorized_drug_categories") or [],
        authorized_therapeutic_areas=data.get("authorized_therapeutic_areas") or [],
        agreement_file_url=data.get("agreement_file_url"),
        supplementary_files=data.get("supplementary_files") or [],
        status="draft",
    )
    db.add(g)
    db.flush()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="management_agreement.create",
        target="management_agreement", target_id=g.id,
        detail={"partner_org_id": g.partner_org_id, "agreement_no": g.agreement_no},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(g)
    return _serialize_agreement(g)


def sign_agreement(db: Session, tenant_id: str, agreement_id: int,
                   user_id: int, user_role: str,
                   signer_holder: str, signer_partner: str) -> dict:
    """签署管理协议"""
    g = _get_agreement_or_raise(db, tenant_id, agreement_id)
    g.signer_holder = signer_holder
    g.signer_partner = signer_partner
    g.signed_at = datetime.utcnow()
    g.status = "active"
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="management_agreement.sign",
        target="management_agreement", target_id=g.id,
        detail={"signer_holder": signer_holder, "signer_partner": signer_partner},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(g)
    return _serialize_agreement(g)


# ──────────────────────────────────────────────
# AuthorizationLetter CRUD
# ──────────────────────────────────────────────

def list_letters(db: Session, tenant_id: str, user_id_filter: int = None,
                 partner_org_id: int = None, status: str = None,
                 page: int = 1, page_size: int = 20) -> dict:
    q = db.query(AuthorizationLetter).filter(
        AuthorizationLetter.tenant_id == tenant_id,
        AuthorizationLetter.is_deleted == 0,
    )
    if user_id_filter:
        q = q.filter(AuthorizationLetter.user_id == user_id_filter)
    if partner_org_id:
        q = q.filter(AuthorizationLetter.partner_org_id == partner_org_id)
    if status:
        q = q.filter(AuthorizationLetter.status == status)
    total = q.count()
    items = q.order_by(AuthorizationLetter.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_letter(l) for l in items],
        "total": total, "page": page, "page_size": page_size,
    }


def get_letter(db: Session, tenant_id: str, letter_id: int) -> dict:
    l = _get_letter_or_raise(db, tenant_id, letter_id)
    return _serialize_letter(l)


def create_letter(db: Session, tenant_id: str, user_id: int, user_role: str, data: dict) -> dict:
    if not data.get("user_id"):
        raise ValidationError("user_id 不能为空")
    l = AuthorizationLetter(
        tenant_id=tenant_id,
        user_id=data["user_id"],
        partner_org_id=data.get("partner_org_id"),
        agreement_id=data.get("agreement_id"),
        letter_no=data.get("letter_no"),
        authorized_regions=data.get("authorized_regions") or [],
        authorized_drug_categories=data.get("authorized_drug_categories") or [],
        authorized_therapeutic_areas=data.get("authorized_therapeutic_areas") or [],
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        letter_file_url=data.get("letter_file_url"),
        status="draft",
    )
    db.add(l)
    db.flush()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="authorization_letter.create",
        target="authorization_letter", target_id=l.id,
        detail={"user_id": l.user_id, "letter_no": l.letter_no},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(l)
    return _serialize_letter(l)


def issue_letter(db: Session, tenant_id: str, letter_id: int,
                 user_id: int, user_role: str) -> dict:
    """颁发授权书"""
    l = _get_letter_or_raise(db, tenant_id, letter_id)
    l.status = "active"
    l.issued_at = datetime.utcnow()
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="authorization_letter.issue",
        target="authorization_letter", target_id=l.id,
        detail={},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(l)
    return _serialize_letter(l)


def revoke_letter(db: Session, tenant_id: str, letter_id: int,
                  user_id: int, user_role: str, reason: str) -> dict:
    """撤销授权书"""
    l = _get_letter_or_raise(db, tenant_id, letter_id)
    l.status = "revoked"
    l.revoked_at = datetime.utcnow()
    l.revoke_reason = reason
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="authorization_letter.revoke",
        target="authorization_letter", target_id=l.id,
        detail={"reason": reason},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(l)
    return _serialize_letter(l)


# ──────────────────────────────────────────────
# 内部辅助
# ──────────────────────────────────────────────

def _get_org_or_raise(db: Session, tenant_id: str, org_id: int) -> PartnerOrganization:
    o = db.query(PartnerOrganization).filter(
        PartnerOrganization.tenant_id == tenant_id,
        PartnerOrganization.is_deleted == 0,
        PartnerOrganization.id == org_id,
    ).first()
    if not o:
        raise NotFoundError("CSO 合作机构不存在")
    return o


def _get_agreement_or_raise(db: Session, tenant_id: str, agreement_id: int) -> ManagementAgreement:
    g = db.query(ManagementAgreement).filter(
        ManagementAgreement.tenant_id == tenant_id,
        ManagementAgreement.is_deleted == 0,
        ManagementAgreement.id == agreement_id,
    ).first()
    if not g:
        raise NotFoundError("管理协议不存在")
    return g


def _get_letter_or_raise(db: Session, tenant_id: str, letter_id: int) -> AuthorizationLetter:
    l = db.query(AuthorizationLetter).filter(
        AuthorizationLetter.tenant_id == tenant_id,
        AuthorizationLetter.is_deleted == 0,
        AuthorizationLetter.id == letter_id,
    ).first()
    if not l:
        raise NotFoundError("授权书不存在")
    return l


def _serialize_org(o: PartnerOrganization) -> dict:
    return {
        "id": o.id,
        "name": o.name,
        "org_code": o.org_code,
        "org_type": o.org_type,
        "legal_person": o.legal_person,
        "contact_name": o.contact_name,
        "contact_phone": o.contact_phone,
        "contact_email": o.contact_email,
        "address": o.address,
        "business_license_url": o.business_license_url,
        "medical_license_url": o.medical_license_url,
        "status": o.status,
        "activated_at": o.activated_at.strftime("%Y-%m-%d %H:%M:%S") if o.activated_at else None,
        "terminated_at": o.terminated_at.strftime("%Y-%m-%d %H:%M:%S") if o.terminated_at else None,
        "credit_score": o.credit_score,
        "is_blacklisted": bool(o.is_blacklisted),
    }


def _serialize_agreement(g: ManagementAgreement) -> dict:
    return {
        "id": g.id,
        "partner_org_id": g.partner_org_id,
        "agreement_no": g.agreement_no,
        "title": g.title,
        "start_date": g.start_date.isoformat() if g.start_date else None,
        "end_date": g.end_date.isoformat() if g.end_date else None,
        "authorized_regions": g.authorized_regions or [],
        "authorized_drug_categories": g.authorized_drug_categories or [],
        "authorized_therapeutic_areas": g.authorized_therapeutic_areas or [],
        "agreement_file_url": g.agreement_file_url,
        "supplementary_files": g.supplementary_files or [],
        "status": g.status,
        "signed_at": g.signed_at.strftime("%Y-%m-%d %H:%M:%S") if g.signed_at else None,
        "signer_holder": g.signer_holder,
        "signer_partner": g.signer_partner,
    }


def _serialize_letter(l: AuthorizationLetter) -> dict:
    return {
        "id": l.id,
        "user_id": l.user_id,
        "partner_org_id": l.partner_org_id,
        "agreement_id": l.agreement_id,
        "letter_no": l.letter_no,
        "authorized_regions": l.authorized_regions or [],
        "authorized_drug_categories": l.authorized_drug_categories or [],
        "authorized_therapeutic_areas": l.authorized_therapeutic_areas or [],
        "start_date": l.start_date.isoformat() if l.start_date else None,
        "end_date": l.end_date.isoformat() if l.end_date else None,
        "letter_file_url": l.letter_file_url,
        "status": l.status,
        "issued_at": l.issued_at.strftime("%Y-%m-%d %H:%M:%S") if l.issued_at else None,
        "revoked_at": l.revoked_at.strftime("%Y-%m-%d %H:%M:%S") if l.revoked_at else None,
        "revoke_reason": l.revoke_reason,
    }
