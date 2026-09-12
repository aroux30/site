"""Support ticket attachment security guard (Karta Phase 6/8 - allowed_user_files).

Implements:
- Magic bytes header inspection (independent of file extension)
- Strict whitelist: JPEG, PNG, PDF, WebP
- Strict blacklist rejection of all executable extensions (.php, .phtml, .exe, .sh, .py, .js, .svg)
- File size enforcement (max 10MB)
"""

from __future__ import annotations

from app.core.exceptions.handlers import ValidationError

# Allowed file signatures (Magic Bytes)
ALLOWED_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "application/pdf": [b"%PDF-"],
    "image/webp": [b"RIFF"],
}

# Dangerous executable or active-content extensions
DANGEROUS_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".php", ".php3", ".php4", ".php5", ".phtml", ".phar",
        ".exe", ".bat", ".cmd", ".sh", ".bash", ".bin",
        ".py", ".pl", ".cgi", ".rb", ".jar",
        ".js", ".ts", ".html", ".htm", ".xhtml", ".svg",
        ".vbs", ".msi", ".dll", ".so",
    }
)

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_ticket_attachment(
    filename: str,
    file_bytes: bytes,
    declared_content_type: str | None = None,
) -> str:
    """Strictly validate attachment content against Magic Bytes and extension whitelist.

    Returns the canonical verified MIME-type on success, or raises ValidationError.
    """
    clean_name = (filename or "").strip().lower()

    if not file_bytes:
        raise ValidationError("فایل ارسالی خالی است")

    if len(file_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValidationError("حجم فایل ارسالی بیش از سقف مجاز (۱۰ مگابایت) است")

    # 1. Extension inspection
    dot_idx = clean_name.rfind(".")
    if dot_idx == -1:
        raise ValidationError("فایل‌های بدون پسوند مجاز نمی‌باشند")

    ext = clean_name[dot_idx:]
    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(f"ارسال فایل با پسوند {ext} به دلایل امنیتی مسدود است")

    allowed_exts = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}
    if ext not in allowed_exts:
        raise ValidationError("تنها فرمت‌های تصویر (JPG, PNG, WebP) و PDF مجاز هستند")

    # 2. Magic Bytes inspection
    detected_mime: str | None = None
    for mime, magic_list in ALLOWED_MAGIC_SIGNATURES.items():
        for magic in magic_list:
            if file_bytes.startswith(magic):
                detected_mime = mime
                break
        if detected_mime:
            break

    # Special check for WebP (RIFF....WEBP)
    if detected_mime == "image/webp" and len(file_bytes) >= 12:
        if file_bytes[8:12] != b"WEBP":
            detected_mime = None

    if not detected_mime:
        raise ValidationError("محتوای فایل ارسالی با پسوند آن مطابقت ندارد یا فایل نامعتبر است")

    return detected_mime
