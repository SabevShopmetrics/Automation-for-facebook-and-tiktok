"""Лог и имейл само при проблем. Един и същ сигнал се праща веднъж."""
import smtplib
from email.message import EmailMessage

from . import sofia_time
from .config import Config
from .state import State


class Notifier:
    def __init__(self, cfg: Config, state: State):
        self.cfg = cfg
        self.state = state
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = cfg.log_dir / "run.log"

    def log(self, message: str) -> None:
        line = f"{sofia_time.to_local(sofia_time.now_utc())}  {message}"
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def alert(self, key: str, subject: str, body: str) -> None:
        """Сигнал към екипа. Повтаря се само ако съдържанието се промени."""
        if self.state.data["alerts"].get(key) == body:
            return
        self.state.data["alerts"][key] = body
        self.log(f"СИГНАЛ: {subject} | {body}")
        with open(self.cfg.log_dir / "alerts.log", "a", encoding="utf-8") as f:
            f.write(f"{sofia_time.to_local(sofia_time.now_utc())}  {subject}\n{body}\n\n")
        if not (self.cfg.smtp_host and self.cfg.alert_to):
            return
        msg = EmailMessage()
        msg["Subject"] = f"[Facebook автопостинг] {subject}"
        msg["From"] = self.cfg.alert_from or self.cfg.smtp_user
        msg["To"] = self.cfg.alert_to
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30) as s:
                s.starttls()
                if self.cfg.smtp_user:
                    s.login(self.cfg.smtp_user, self.cfg.smtp_password)
                s.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            self.log(f"Имейлът не тръгна: {e}")

    def clear(self, key: str) -> None:
        self.state.data["alerts"].pop(key, None)
