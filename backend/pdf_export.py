"""Shared Markdown PDF export; use installed Chromium on Windows."""
from __future__ import annotations

import asyncio
import html
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlparse

import mistune
from bs4 import BeautifulSoup

PRINT_CSS = """
@page { size: A4; margin: 18mm 17mm; }
html { background: white; }
body { font-family: 'Microsoft YaHei', 'Noto Sans CJK SC', Arial, sans-serif;
       font-size: 11pt; line-height: 1.65; color: #20262e; margin: 0; }
h1,h2,h3,h4 { line-height: 1.35; break-after: avoid; color: #17364d; }
h1 { font-size: 21pt; } h2 { font-size: 16pt; } h3 { font-size: 13pt; }
p,li { overflow-wrap: anywhere; } a { color: #185c91; overflow-wrap: anywhere; }
table { width: 100%; border-collapse: collapse; margin: 12pt 0; font-size: 9pt; }
th,td { border: 1px solid #bcc7ce; padding: 5pt; text-align: left; overflow-wrap: anywhere; }
th { background: #edf3f6; } thead { display: table-header-group; } tr { break-inside: avoid; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f8; padding: 8pt; }
code { font-family: Consolas, 'Microsoft YaHei', monospace; font-size: 9pt; }
blockquote { margin: 12pt 0; border-left: 3pt solid #c0d4df; padding-left: 10pt; color: #475361; }
img { max-width: 100%; max-height: 220mm; object-fit: contain; } hr { border: 0; border-top: 1px solid #ccd5db; }
"""


def _find_browser() -> Path:
    override = os.environ.get("PDF_BROWSER_PATH")
    if override:
        browser = Path(override)
        if browser.is_file():
            return browser
        raise RuntimeError("PDF_BROWSER_PATH does not point to a browser executable")
    candidates = []
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = Path(os.environ.get(env_name, "C:/Program Files"))
        candidates.extend([root / "Google/Chrome/Application/chrome.exe", root / "Microsoft/Edge/Application/msedge.exe"])
    for browser in candidates:
        if browser.is_file():
            return browser
    for name in ("chrome", "msedge", "chromium"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError("PDF export requires installed Chrome or Edge on Windows; set PDF_BROWSER_PATH if necessary")


def _html_document(markdown: str, project_root: Path) -> str:
    renderer = mistune.create_markdown(escape=True, plugins=["table", "strikethrough", "url"])
    soup = BeautifulSoup(renderer(str(markdown)), "html.parser")
    outputs = (project_root / "outputs").resolve()
    # Reports may contain remote images or guessed file paths. Only local output assets
    # and inline images are eligible; rendering does not fetch arbitrary web assets.
    for image in soup.find_all("img"):
        src = str(image.get("src", ""))
        if src.startswith("data:image/"):
            continue
        candidate = None
        if src.startswith("/outputs/"):
            candidate = project_root / unquote(src.lstrip("/"))
        elif src.startswith("file:"):
            raw = unquote(urlparse(src).path)
            if os.name == "nt" and raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
                raw = raw[1:]
            candidate = Path(raw)
        elif not urlparse(src).scheme:
            candidate = project_root / unquote(src)
        if candidate is not None:
            candidate = candidate.resolve()
        if candidate is not None and candidate.is_relative_to(outputs) and candidate.is_file():
            image["src"] = candidate.as_uri()
        else:
            image.replace_with("[" + str(image.get("alt", "图片")) + "]")
    title = soup.find("h1")
    title_text = title.get_text() if title else "PaperPilot research report"
    policy = "default-src 'none'; img-src file: data:; style-src 'unsafe-inline'; font-src file: data:; script-src 'none'"
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">'
        f'<title>{html.escape(title_text)}</title><style>{PRINT_CSS}</style>'
        f'</head><body>{soup}</body></html>'
    )


def _validate_pdf(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < 512:
        raise RuntimeError("PDF renderer produced no usable output")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise RuntimeError("PDF renderer produced an invalid file")


def _render_pdf(markdown: str, file_path: str, base_url: str | None = None) -> None:
    target = Path(file_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    root = Path(base_url or os.getcwd()).resolve()
    document = _html_document(markdown, root)
    # A unique browser profile prevents report exports from reusing the user's open browser.
    with tempfile.TemporaryDirectory(prefix=".paperpilot-pdf-", dir=target.parent) as temp_dir:
        temporary = Path(temp_dir).resolve()
        if not temporary.is_relative_to(target.parent):
            raise RuntimeError("Unexpected PDF temporary directory")
        generated = temporary / "report.pdf"
        if os.name == "nt":
            browser = _find_browser()
            source = temporary / "report.html"
            source.write_text(document, encoding="utf-8")
            command = [
                str(browser), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking", "--disable-component-update",
                "--disable-sync", "--no-pdf-header-footer", "--allow-file-access-from-files", "--timeout=15000",
                f"--user-data-dir={temporary / 'profile'}", f"--print-to-pdf={generated}", source.as_uri(),
            ]
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if completed.returncode:
                raise RuntimeError(f"Browser PDF export failed (exit {completed.returncode})")
        else:
            from weasyprint import HTML
            HTML(string=document, base_url=str(root)).write_pdf(str(generated))
        _validate_pdf(generated)
        os.replace(generated, target)


async def write_markdown_pdf(markdown: str, file_path: str, base_url: str | None = None) -> None:
    """Keep blocking browser startup and printing off the server's event loop."""
    await asyncio.to_thread(_render_pdf, markdown, file_path, base_url)
