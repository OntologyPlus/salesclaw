"""Phase 3 监管报送适配器层（外部平台对接骨架）。

设计目标：把"内部合规数据包"（RegulatorySubmission.payload，结构化 JSON 通用包）
与"外部监管平台 API"（省级药监/卫健报送接口）解耦。

- SubmissionExporter：把 payload 序列化为 json / csv 两种可下载格式（csv 为违规明细扁平化）。
- ExternalRegulatoryClient：基于配置的 REGULATORY_SUBMISSION_ENDPOINT 推送数据包，
  采用可替换的鉴权头（默认 Bearer），回执号写入 RegulatorySubmission.external_ref。
  若未配置外部端点，则进入 dry-run 模式（仅返回结构化回执占位，不发起网络请求）。

真实客户现场接入时，只需：
1) 在 .env 配置 REGULATORY_SUBMISSION_ENDPOINT / REGULATORY_SUBMISSION_TOKEN；
2) （可选）继承 ExternalRegulatoryClient 覆写 `_build_request_body` / `_parse_receipt`
   以适配具体省份的字段映射与回执结构。
"""
import csv
import io
import json
from typing import Optional

import httpx

from config import settings
from core.exceptions import ValidationError


# ──────────────────────────────────────────────
# 导出器：payload → 可下载文件内容
# ──────────────────────────────────────────────

class SubmissionExporter:
    """把结构化报送 payload 序列化为 json / csv。"""

    @staticmethod
    def to_json(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def to_csv(payload: dict) -> str:
        """CSV 仅导出违规明细（violations 数组），其余摘要写入首部注释行。"""
        output = io.StringIO()
        summary = payload.get("summary", {})
        output.write(f"# period={payload.get('period_value')} "
                     f"type={payload.get('submission_type')} "
                     f"violation_total={summary.get('violation_total', 0)}\n")
        rows = payload.get("violations", [])
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        else:
            output.write("# (no violations in this period)\n")
        return output.getvalue()

    @classmethod
    def export(cls, payload: dict, fmt: str) -> str:
        fmt = (fmt or "json").lower()
        if fmt == "csv":
            return cls.to_csv(payload)
        if fmt == "json":
            return cls.to_json(payload)
        raise ValidationError(f"不支持的导出格式: {fmt}（仅 json/csv）")


# ──────────────────────────────────────────────
# 外部平台客户端：推送数据包（可替换鉴权/字段映射）
# ──────────────────────────────────────────────

class ExternalRegulatoryClient:
    """向外部监管平台报送数据包的 HTTP 客户端。

    默认实现：POST {ENDPOINT}/submissions，Bearer 鉴权，JSON body。
    dry-run（未配置端点）时返回占位回执，不联网。
    """

    def __init__(self, endpoint: Optional[str] = None, token: Optional[str] = None):
        self.endpoint = endpoint or settings.REGULATORY_SUBMISSION_ENDPOINT
        self.token = token or settings.REGULATORY_SUBMISSION_TOKEN
        self.timeout = settings.REGULATORY_SUBMISSION_TIMEOUT

    @property
    def dry_run(self) -> bool:
        return not bool(self.endpoint)

    def _build_request_body(self, payload: dict, submission_id: int) -> dict:
        """构造外推请求体（默认即原 payload；省份差异在此覆写字段映射）。"""
        return {
            "source_submission_id": submission_id,
            "payload": payload,
        }

    def _make_client(self) -> httpx.Client:
        """创建底层 httpx 客户端（可覆写以注入 MockTransport 便于测试）。"""
        return httpx.Client(timeout=self.timeout)

    def _parse_receipt(self, resp: httpx.Response) -> str:
        """从响应中解析外部回执号（默认取 JSON 的 receipt_no / id）。"""
        try:
            data = resp.json()
        except Exception:
            return resp.headers.get("X-Receipt-Id", f"receipt-{resp.status_code}")
        return str(data.get("receipt_no") or data.get("id") or f"receipt-{resp.status_code}")

    def push(self, payload: dict, submission_id: int) -> dict:
        """推送数据包，返回 {dry_run, external_ref, status, detail}。"""
        if self.dry_run:
            return {
                "dry_run": True,
                "external_ref": f"DRYRUN-{submission_id}",
                "status": "dry_run",
                "detail": "未配置 REGULATORY_SUBMISSION_ENDPOINT，仅本地生成占位回执，未实际外推。",
            }
        body = self._build_request_body(payload, submission_id)
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            client = self._make_client()
            resp = client.post(
                f"{self.endpoint.rstrip('/')}/submissions",
                json=body, headers=headers,
            )
            resp.raise_for_status()
            client.close()
            return {
                "dry_run": False,
                "external_ref": self._parse_receipt(resp),
                "status": "submitted",
                "detail": f"HTTP {resp.status_code}",
            }
        except httpx.HTTPStatusError as e:
            raise ValidationError(f"监管平台返回错误: {e.response.status_code} {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise ValidationError(f"无法连接监管平台: {str(e)}")
