"""统一异常定义"""


class AppException(Exception):
    """应用基础异常"""
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str = "参数错误"):
        super().__init__(10001, message, 422)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "未登录"):
        super().__init__(20001, message, 401)


class TokenExpiredError(AppException):
    def __init__(self, message: str = "Token 过期"):
        super().__init__(20002, message, 401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "权限不足"):
        super().__init__(20003, message, 403)


class TenantMismatchError(AppException):
    def __init__(self, message: str = "租户不匹配"):
        super().__init__(20004, message, 403)


class NotFoundError(AppException):
    def __init__(self, message: str = "数据不存在"):
        super().__init__(40001, message, 404)


class DataDuplicateError(AppException):
    def __init__(self, message: str = "数据重复"):
        super().__init__(40002, message, 409)


class DataConflictError(AppException):
    def __init__(self, message: str = "数据冲突"):
        super().__init__(40003, message, 409)


class InternalError(AppException):
    def __init__(self, message: str = "内部错误"):
        super().__init__(90001, message, 500)
