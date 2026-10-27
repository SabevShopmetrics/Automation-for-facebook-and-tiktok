"""Графикът: един ред = един TikTok клип."""
import csv
import io
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from . import sofia_time

COLUMNS = ["id", "publish_at", "drive_path", "caption", "needs_approval", "approved", "notes"]


@dataclass
class Row:
    id: str
    publish_at: datetime | None
    publish_at_text: str
    drive_path: str
    caption: str
    needs_approval: bool
    approved: bool
    notes: str

    @property
    def file_name(self) -> str:
        return self.drive_path.rsplit("/", 1)[-1]


def _yes(value: str) -> bool:
    return value.strip().lower() in {"да", "yes", "y", "1", "true", "x"}


def _read_text(csv_path, csv_url) -> str:
    if csv_url:
        req = urllib.request.Request(csv_url, headers={"User-Agent": "tiktok-autopost"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8-sig")
    return csv_path.read_text(encoding="utf-8-sig")


def load(csv_path, csv_url: str = "") -> list[Row]:
    reader = csv.DictReader(io.StringIO(_read_text(csv_path, csv_url)))
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"В графика липсват колони: {', '.join(missing)}")
    rows, seen = [], set()
    for raw in reader:
        rid = (raw["id"] or "").strip()
        if not rid:
            continue
        if rid in seen:
            raise ValueError(f"Повтарящ се id в графика: {rid}")
        seen.add(rid)
        when_text = (raw["publish_at"] or "").strip()
        rows.append(Row(
            id=rid,
            publish_at=sofia_time.parse_local(when_text) if when_text else None,
            publish_at_text=when_text,
            drive_path=(raw["drive_path"] or "").strip(),
            caption=(raw["caption"] or "").strip(),
            needs_approval=_yes(raw["needs_approval"] or ""),
            approved=_yes(raw["approved"] or ""),
            notes=(raw["notes"] or "").strip(),
        ))
    return rows
