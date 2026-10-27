"""Настройки от файла .env."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Видеата се кешират извън проекта, за да не се синхронизират с OneDrive.
DEFAULT_CACHE = (Path(os.environ["LOCALAPPDATA"]) / "tiktok-autopost" / "cache") if os.environ.get("LOCALAPPDATA") else ROOT / "cache"


def _load_env(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass
class Config:
    premiere_at: str
    drive_folder_id: str
    drive_local_dir: str
    schedule_csv: Path
    schedule_csv_url: str
    cache_dir: Path
    state_file: Path
    log_dir: Path
    host: str
    port: int
    tool_url: str
    tool_token: str
    window_days: int
    check_minutes: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    alert_from: str
    alert_to: str


def load(env_file: Path | None = None) -> Config:
    env = _load_env(env_file or ROOT / ".env")

    def get(key, default=""):
        return os.environ.get(key, env.get(key, default))

    def path(key, default):
        p = Path(get(key, default))
        return p if p.is_absolute() else ROOT / p

    port = int(get("PORT", "8765"))
    return Config(
        premiere_at=get("PREMIERE_AT", "2026-11-01 10:00"),
        drive_folder_id=get("DRIVE_FOLDER_ID"),
        drive_local_dir=get("DRIVE_LOCAL_DIR"),
        schedule_csv=path("SCHEDULE_CSV", "data/schedule.csv"),
        schedule_csv_url=get("SCHEDULE_CSV_URL"),
        cache_dir=path("CACHE_DIR", str(DEFAULT_CACHE)),
        state_file=path("STATE_FILE", "data/state.json"),
        log_dir=path("LOG_DIR", "logs"),
        host=get("HOST", "127.0.0.1"),
        port=port,
        tool_url=get("TOOL_URL", f"http://localhost:{port}/"),
        tool_token=get("TOOL_TOKEN"),
        window_days=int(get("WINDOW_DAYS", "9")),
        check_minutes=int(get("CHECK_MINUTES", "10")),
        smtp_host=get("SMTP_HOST"),
        smtp_port=int(get("SMTP_PORT", "587")),
        smtp_user=get("SMTP_USER"),
        smtp_password=get("SMTP_PASSWORD"),
        alert_from=get("ALERT_FROM"),
        alert_to=get("ALERT_TO"),
    )
