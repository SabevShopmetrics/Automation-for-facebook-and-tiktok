"""Правилата от плана за пускане, проверявани за всеки TikTok клип."""
import re

from . import sofia_time
from .schedule import Row

HASHTAG = re.compile(r"#\w+", re.UNICODE)
DEATH_TOLL = re.compile(r"(\d+)\s+(души|човека|загинал)", re.IGNORECASE)
CAPTION_LIMIT = 2200


def check(row: Row, premiere_at: str) -> list[str]:
    errors = []
    if row.publish_at is None:
        errors.append("липсва дата и час")
    if "/9x16/" not in f"/{row.drive_path}":
        errors.append("за TikTok файлът трябва да е от папка 9x16")
    if not row.caption:
        errors.append("липсва текст")
    if len(row.caption) > CAPTION_LIMIT:
        errors.append(f"текстът е {len(row.caption)} знака, TikTok позволява {CAPTION_LIMIT}")
    tags = HASHTAG.findall(row.caption)
    if not 3 <= len(tags) <= 5:
        errors.append(f"хаштаговете са {len(tags)}, трябва 3–5")
    text = row.caption.lower()
    if row.publish_at is not None:
        before = row.publish_at < sofia_time.parse_local(premiere_at)
        if before and "премиер" not in text:
            errors.append("преди премиерата текстът трябва да покани за премиерата")
        if not before and "разговор" not in text:
            errors.append("след премиерата текстът трябва да насочва към целия разговор")
    if "девня" in text or "взрив" in text:
        for number, _ in DEATH_TOLL.findall(row.caption):
            if number != "22":
                errors.append(f"броят загинали в текста е {number}, трябва да е 22")
    if "чернобил" in text:
        errors.append("без сравнения с Чернобил")
    return errors


def blocked_by_approval(row: Row) -> bool:
    return row.needs_approval and not row.approved
