"""Resolve report follow-up context without guessing another user's latest report."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote


def resolve_report_context(payload: dict, project_root: Path, connection_context: dict | None = None):
    outputs = (Path(project_root) / "outputs").resolve()
    report_path = payload.get("report_path")
    report_id = payload.get("report_id")
    text = None
    reference = None
    source = None
    if report_path or report_id:
        if report_path:
            if not isinstance(report_path, str):
                raise ValueError("报告文件标识无效")
            relative = unquote(report_path).replace("\\", "/").lstrip("/")
            if not relative.startswith("outputs/"):
                raise ValueError("报告文件必须位于outputs目录")
            candidate = (Path(project_root) / relative).resolve()
        else:
            if not isinstance(report_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", report_id):
                raise ValueError("报告编号无效")
            candidate = (outputs / f"{report_id}.md").resolve()
        if not candidate.is_relative_to(outputs) or candidate.suffix.lower() != ".md":
            raise ValueError("报告文件必须是outputs目录中的Markdown文件")
        if not candidate.is_file():
            raise ValueError("未找到所选报告文件，请重新打开已保存的报告")
        text = candidate.read_text(encoding="utf-8")
        reference = candidate.stem
        source = "saved_markdown"
    elif isinstance(payload.get("report"), str) and payload["report"].strip():
        text = payload["report"]
        source = "request_body"
    elif isinstance(connection_context, dict) and isinstance(connection_context.get("report"), str):
        text = connection_context["report"]
        reference = connection_context.get("report_id")
        source = "same_connection"
    if not isinstance(text, str) or not text.strip():
        raise ValueError("未收到所讨论报告的正文，请刷新页面并打开已保存的报告后再提问")
    metadata = {"source": source, "report_id": reference, "characters": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return text, metadata
