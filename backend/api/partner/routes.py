"""合作伙伴（CSO）管理 API（v2.2 Phase 2）

对应《医药代表管理办法》第 8 条 CSO 委托管理：
- 持有人可委托 CSO 进行医药代表管理，但需签订管理协议 + 授权书
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import partner_service

router = APIRouter(prefix="/partner")


# ──────────────────────────────────────────────
# 请求模型
# ──────────────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str
    org_code: Optional[str] = None
    org_type: str = "cso"
    legal_person: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    business_license_url: Optional[str] = None
    medical_license_url: Optional[str] = None


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    org_code: Optional[str] = None
    org_type: Optional[str] = None
    legal_person: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    business_license_url: Optional[str] = None
    medical_license_url: Optional[str] = None
    status: Optional[str] = None
    credit_score: Optional[int] = None
    is_blacklisted: Optional[int] = None


class CreateAgreementRequest(BaseModel):
    partner_org_id: int
    agreement_no: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    authorized_regions: Optional[List[str]] = None
    authorized_drug_categories: Optional[List[str]] = None
    authorized_therapeutic_areas: Optional[List[str]] = None
    agreement_file_url: Optional[str] = None
    supplementary_files: Optional[List[Dict[str, Any]]] = None


class SignAgreementRequest(BaseModel):
    signer_holder: str
    signer_partner: str


class CreateLetterRequest(BaseModel):
    user_id: int
    partner_org_id: Optional[int] = None
    agreement_id: Optional[int] = None
    letter_no: Optional[str] = None
    authorized_regions: Optional[List[str]] = None
    authorized_drug_categories: Optional[List[str]] = None
    authorized_therapeutic_areas: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    letter_file_url: Optional[str] = None


class RevokeLetterRequest(BaseModel):
    reason: str


# ──────────────────────────────────────────────
# PartnerOrganization
# ──────────────────────────────────────────────

@router.get("/organizations")
async def list_organizations(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CSO 合作机构列表"""
    return unified_response(
        partner_service.list_organizations(db, user.tenant_id, status, page, page_size)
    )


@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CSO 机构详情"""
    return unified_response(partner_service.get_organization(db, user.tenant_id, org_id))


@router.post("/organizations")
async def create_organization(
    req: CreateOrgRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建 CSO 合作机构"""
    return unified_response(
        partner_service.create_organization(
            db, user.tenant_id, user.id, "compliance_officer", req.model_dump(),
        )
    )


@router.put("/organizations/{org_id}")
async def update_organization(
    org_id: int,
    req: UpdateOrgRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新 CSO 机构"""
    data = req.model_dump(exclude_none=True)
    return unified_response(
        partner_service.update_organization(
            db, user.tenant_id, org_id, user.id, "compliance_officer", data,
        )
    )


@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除 CSO 机构"""
    partner_service.delete_organization(db, user.tenant_id, org_id, user.id, "compliance_officer")
    return unified_response({"deleted": True, "id": org_id})


# ──────────────────────────────────────────────
# ManagementAgreement
# ──────────────────────────────────────────────

@router.get("/agreements")
async def list_agreements(
    partner_org_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理协议列表"""
    return unified_response(
        partner_service.list_agreements(
            db, user.tenant_id, partner_org_id, status, page, page_size,
        )
    )


@router.get("/agreements/{agreement_id}")
async def get_agreement(
    agreement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理协议详情"""
    return unified_response(partner_service.get_agreement(db, user.tenant_id, agreement_id))


@router.post("/agreements")
async def create_agreement(
    req: CreateAgreementRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建管理协议"""
    return unified_response(
        partner_service.create_agreement(
            db, user.tenant_id, user.id, "compliance_officer", req.model_dump(),
        )
    )


@router.post("/agreements/{agreement_id}/sign")
async def sign_agreement(
    agreement_id: int,
    req: SignAgreementRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """签署管理协议"""
    return unified_response(
        partner_service.sign_agreement(
            db, user.tenant_id, agreement_id, user.id, "compliance_officer",
            req.signer_holder, req.signer_partner,
        )
    )


# ──────────────────────────────────────────────
# AuthorizationLetter
# ──────────────────────────────────────────────

@router.get("/letters")
async def list_letters(
    user_id_filter: Optional[int] = Query(None, alias="user_id"),
    partner_org_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """授权书列表"""
    return unified_response(
        partner_service.list_letters(
            db, user.tenant_id, user_id_filter, partner_org_id, status, page, page_size,
        )
    )


@router.get("/letters/{letter_id}")
async def get_letter(
    letter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """授权书详情"""
    return unified_response(partner_service.get_letter(db, user.tenant_id, letter_id))


@router.post("/letters")
async def create_letter(
    req: CreateLetterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建授权书"""
    return unified_response(
        partner_service.create_letter(
            db, user.tenant_id, user.id, "compliance_officer", req.model_dump(),
        )
    )


@router.post("/letters/{letter_id}/issue")
async def issue_letter(
    letter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """颁发授权书"""
    return unified_response(
        partner_service.issue_letter(
            db, user.tenant_id, letter_id, user.id, "compliance_officer",
        )
    )


@router.post("/letters/{letter_id}/revoke")
async def revoke_letter(
    letter_id: int,
    req: RevokeLetterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """撤销授权书"""
    return unified_response(
        partner_service.revoke_letter(
            db, user.tenant_id, letter_id, user.id, "compliance_officer", req.reason,
        )
    )
