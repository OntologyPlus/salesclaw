"""演示数据：上岗三件套 + 学术活动三流 + 违规事件（幂等）

供 AcademicBoard / Violation / AuditPack / 对话式工作流联调。
在 bootstrap.seed.run_all 中注册。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def seed_pharma_workflows() -> int:
    """幂等写入 demo 租户下的合规/学术演示数据。返回新增条数（近似）。"""
    from database import (
        AcademicActivity,
        BusinessSessionLocal,
        ComplianceCommitment,
        ComplianceViolationEvent,
        Course,
        CourseEnrollment,
        Exam,
        ExamRecord,
        PharmaRepProfile,
        Tenant,
        User,
    )

    added = 0
    with BusinessSessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == "demo").first()
        if not tenant:
            return 0
        tid = str(tenant.id)
        user = db.query(User).filter(
            User.tenant_id == tid,
            User.username == "admin",
            User.is_deleted == 0,
        ).first()
        if not user:
            user = db.query(User).filter(
                User.tenant_id == tid, User.is_deleted == 0,
            ).order_by(User.id.asc()).first()
        if not user:
            return 0
        uid = user.id

        # 1) 合规必修课
        course = db.query(Course).filter(
            Course.tenant_id == tid,
            Course.is_deleted == 0,
            Course.title == "医药合规培训",
        ).first()
        if course:
            changed = False
            if not course.is_compliance:
                course.is_compliance = 1
                changed = True
            if not course.is_mandatory:
                course.is_mandatory = 1
                changed = True
            if changed:
                added += 1
        else:
            course = Course(
                tenant_id=tid,
                title="医药合规培训",
                description="医药行业合规要求、学术推广边界与反商业贿赂要点。",
                course_type="article",
                category="合规",
                difficulty="advanced",
                duration_minutes=60,
                tags=["合规", "法规"],
                is_published=1,
                is_compliance=1,
                is_mandatory=1,
                enroll_count=1,
                avg_rating=85,
            )
            db.add(course)
            db.flush()
            added += 1

        # 2) 选课完成
        enr = db.query(CourseEnrollment).filter(
            CourseEnrollment.tenant_id == tid,
            CourseEnrollment.user_id == uid,
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.is_deleted == 0,
        ).first()
        if not enr:
            db.add(CourseEnrollment(
                tenant_id=tid,
                user_id=uid,
                course_id=course.id,
                status="completed",
                progress=100,
            ))
            added += 1

        # 3) 考核通过（任意已通过记录即可；否则补一条合规考核）
        passed_er = db.query(ExamRecord).filter(
            ExamRecord.tenant_id == tid,
            ExamRecord.user_id == uid,
            ExamRecord.is_deleted == 0,
            ExamRecord.passed == 1,
        ).first()
        if not passed_er:
            exam = db.query(Exam).filter(
                Exam.tenant_id == tid,
                Exam.is_deleted == 0,
                Exam.status == "published",
            ).first()
            if not exam:
                exam = Exam(
                    tenant_id=tid,
                    title="医药合规考核",
                    description="合规培训结业考核",
                    duration_minutes=30,
                    pass_score=60,
                    status="published",
                )
                db.add(exam)
                db.flush()
                added += 1
            db.add(ExamRecord(
                tenant_id=tid,
                user_id=uid,
                exam_id=exam.id,
                status="submitted",
                score=90,
                passed=1,
                submitted_at=datetime.utcnow(),
            ))
            added += 1

        # 4) 承诺书 + 备案档案
        commitment = db.query(ComplianceCommitment).filter(
            ComplianceCommitment.tenant_id == tid,
            ComplianceCommitment.user_id == uid,
            ComplianceCommitment.is_deleted == 0,
            ComplianceCommitment.commitment_type == "onboarding",
        ).first()
        if not commitment:
            commitment = ComplianceCommitment(
                tenant_id=tid,
                user_id=uid,
                commitment_type="onboarding",
                course_id=course.id,
                commitment_text="本人承诺严格遵守《医药代表管理办法》及公司合规制度。",
                version="1.0",
                signed_at=datetime.utcnow() - timedelta(days=10),
                status="signed",
            )
            db.add(commitment)
            db.flush()
            added += 1

        profile = db.query(PharmaRepProfile).filter(
            PharmaRepProfile.tenant_id == tid,
            PharmaRepProfile.user_id == uid,
            PharmaRepProfile.is_deleted == 0,
        ).first()
        if not profile:
            profile = PharmaRepProfile(
                tenant_id=tid,
                user_id=uid,
                id_card_type="身份证",
                id_card_no="320102199001011234",
                gender="男",
                education_level="本科",
                major="药学",
                contract_start=date(2024, 1, 1),
                contract_end=date(2027, 12, 31),
                drug_categories=["心血管"],
                therapeutic_areas=["心内科"],
                authorized_regions=["江苏省"],
                authenticity_statement="本人声明备案信息真实准确。",
                statement_signed_at=datetime.utcnow() - timedelta(days=10),
                commitment_id=commitment.id,
                registration_no=f"PR-{tid}-{uid}-DEMO",
                registration_status="submitted",
                registered_at=datetime.utcnow() - timedelta(days=9),
            )
            db.add(profile)
            added += 1
        else:
            if not profile.commitment_id:
                profile.commitment_id = commitment.id
                added += 1
            if not profile.registration_no:
                profile.registration_no = f"PR-{tid}-{uid}-DEMO"
                profile.registration_status = "submitted"
                profile.registered_at = profile.registered_at or datetime.utcnow()
                added += 1

        # 5) 学术活动样例（按标题幂等）
        samples = [
            {
                "title": "心血通科室会（演示·已审批）",
                "activity_type": "academic_meeting",
                "status": "approved",
                "planned_at": datetime.utcnow() + timedelta(days=7),
                "location": "市第一人民医院心内科示教室",
                "meeting_protocol": {"protocol_no": "PROT-DEMO-001", "signed": True},
                "checkin_evidence": [],
                "expense_vouchers": [],
                "total_expense": 0,
                "violation_count": 0,
            },
            {
                "title": "脑复康学术沙龙（演示·进行中）",
                "activity_type": "lecture",
                "status": "ongoing",
                "planned_at": datetime.utcnow() - timedelta(days=1),
                "location": "市第二医院学术厅",
                "meeting_protocol": {"protocol_no": "PROT-DEMO-002", "signed": True},
                "checkin_evidence": [
                    {"name": "张医生", "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")},
                ],
                "expense_vouchers": [],
                "total_expense": 0,
                "violation_count": 0,
            },
            {
                "title": "合理用药巡讲（演示·已归档）",
                "activity_type": "conference",
                "status": "archived",
                "planned_at": datetime.utcnow() - timedelta(days=30),
                "ended_at": datetime.utcnow() - timedelta(days=29),
                "location": "南京国际会议中心",
                "meeting_protocol": {"protocol_no": "PROT-DEMO-003", "signed": True},
                "checkin_evidence": [
                    {"name": "王教授", "checked_at": "2026-09-01 09:00:00"},
                    {"name": "李主任", "checked_at": "2026-09-01 09:05:00"},
                ],
                "expense_vouchers": [
                    {"amount": 80000, "type": "venue", "invoice_no": "INV-DEMO-001"},
                ],
                "total_expense": 80000,
                "violation_count": 0,
                "feedback_summary": "内容合规，反馈良好。",
            },
            {
                "title": "边界案例会（演示·含违规）",
                "activity_type": "ward_round",
                "status": "ongoing",
                "planned_at": datetime.utcnow() - timedelta(days=3),
                "location": "社区卫生服务中心",
                "meeting_protocol": {"protocol_no": "PROT-DEMO-004"},
                "checkin_evidence": [{"name": "陈医生"}],
                "expense_vouchers": [{"amount": 120000, "type": "catering"}],
                "total_expense": 120000,
                "violation_count": 1,
            },
        ]

        activity_ids: dict[str, int] = {}
        for s in samples:
            exists = db.query(AcademicActivity).filter(
                AcademicActivity.tenant_id == tid,
                AcademicActivity.is_deleted == 0,
                AcademicActivity.title == s["title"],
            ).first()
            if exists:
                activity_ids[s["title"]] = exists.id
                continue
            act = AcademicActivity(
                tenant_id=tid,
                title=s["title"],
                activity_type=s["activity_type"],
                planned_at=s.get("planned_at"),
                ended_at=s.get("ended_at"),
                location=s.get("location"),
                province="江苏",
                city="南京",
                pharma_rep_user_id=uid,
                meeting_protocol=s.get("meeting_protocol") or {},
                checkin_evidence=s.get("checkin_evidence") or [],
                expense_vouchers=s.get("expense_vouchers") or [],
                total_expense=s.get("total_expense") or 0,
                status=s["status"],
                violation_count=s.get("violation_count") or 0,
                feedback_summary=s.get("feedback_summary"),
                onboarding_checked=1,
                gates_passed=["G1", "G2", "G3"],
            )
            db.add(act)
            db.flush()
            activity_ids[s["title"]] = act.id
            added += 1

        # 6) 违规事件（关联边界案例会）
        viol_title = "边界案例会（演示·含违规）"
        viol_aid = activity_ids.get(viol_title)
        if viol_aid:
            ve = db.query(ComplianceViolationEvent).filter(
                ComplianceViolationEvent.tenant_id == tid,
                ComplianceViolationEvent.is_deleted == 0,
                ComplianceViolationEvent.entity_type == "academic_activity",
                ComplianceViolationEvent.entity_id == viol_aid,
            ).first()
            if not ve:
                db.add(ComplianceViolationEvent(
                    tenant_id=tid,
                    rule_code="V-EXPENSE-001",
                    rule_article="第11条",
                    rule_subject="expense",
                    severity="high",
                    actor_id=uid,
                    actor_role="pharma_rep",
                    entity_type="academic_activity",
                    entity_id=viol_aid,
                    description="演示：费用凭证与活动规模不匹配，待合规复核。",
                    evidence_payload={"activity_id": viol_aid, "amount": 120000},
                    status="open",
                ))
                added += 1

        db.commit()
    return added
