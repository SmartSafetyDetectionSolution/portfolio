import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
OUTBOX_LOG = DATA_DIR / "email_outbox.log"


def _log_line(message: str) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with OUTBOX_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def send_verification_email(email_config: Dict[str, Any], to_email: str, verify_url: str) -> bool:
    to_email = (to_email or "").strip()
    verify_url = (verify_url or "").strip()
    if not to_email or not verify_url:
        return False

    dev_mode = bool(email_config.get("dev_mode", True))
    smtp_host = str(email_config.get("smtp_host", "")).strip()
    smtp_port = int(email_config.get("smtp_port", 587) or 587)
    smtp_user = str(email_config.get("smtp_user", "")).strip()
    smtp_password = str(email_config.get("smtp_password", "")).strip()
    use_tls = bool(email_config.get("use_tls", True))
    sender = str(email_config.get("sender", "")).strip() or (smtp_user or "no-reply@example.local")

    subject = "안전장비 모니터링 이메일 인증"
    body_text = (
        "안전장비 모니터링 서비스 회원가입 이메일 인증 링크입니다.\n\n"
        f"{verify_url}\n\n"
        "이 링크를 클릭하면 인증이 완료됩니다.\n"
    )

    if dev_mode or not smtp_host:
        _log_line(f"DEV send to={to_email} url={verify_url}")
        return True

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message.set_content(body_text)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        _log_line(f"SMTP send ok to={to_email}")
        return True
    except Exception as error:
        _log_line(f"SMTP send failed to={to_email} err={error}")
        return False
