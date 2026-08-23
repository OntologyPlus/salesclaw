"""常用验证器"""
import re


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w.-]+@[\w.-]+\.\w+$", email))


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def validate_tenant_code(code: str) -> bool:
    return bool(re.match(r"^[a-z0-9_-]{2,32}$", code))
