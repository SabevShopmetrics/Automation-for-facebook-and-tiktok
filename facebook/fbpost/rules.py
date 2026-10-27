"""Правилата от плана за пускане, проверявани преди всяка публикация."""
import re

from . import sofia_time
from .schedule import TYPES, Row

HASHTAG = re.compile(r"#\w+", re.UNICODE)
DEATH_TOLL = re.compile(r"(\d+)\s+(души|човека|загинал)", re.IGNORECASE)
REEL_MAX_SECONDS = 90


def check(row: Row, premiere_at: str, youtube_url: str) -> list[str]:
    """Грешки, заради които редът не бива да се публикува."""
    errors = []
    if row.type not in TYPES:
        errors.append(f"непознат тип '{row.type}' (позволени: {', '.join(sorted(TYPES))})")
    if row.publish_at is None:
        errors.append("липсва дата и час")
    expected_folder = {"reel": "/9x16/", "feed_video": "/4x5/"}.get(row.type)
    if expected_folder and expected_folder not in f"/{row.drive_path}":
        errors.append(f"файлът не е от папка {expected_folder.strip('/')} за тип {row.type}")
    if not row.caption:
        errors.append("липсва текст")
    tags = HASHTAG.findall(row.caption)
    if not 3 <= len(tags) <= 5:
        errors.append(f"хаштаговете са {len(tags)}, трябва 3–5")
    text = row.caption.lower()
    if row.publish_at is not None:
        before = row.publish_at < sofia_time.parse_local(premiere_at)
        if before and "премиер" not in text:
            errors.append("преди премиерата текстът трябва да покани за премиерата")
        if not before and "пълния разговор" not in text:
            errors.append("след премиерата текстът трябва да съдържа „Гледайте пълния разговор в YouTube“")
    if "девня" in text or "взрив" in text:
        for number, _ in DEATH_TOLL.findall(row.caption):
            if number != "22":
                errors.append(f"броят загинали в текста е {number}, трябва да е 22")
    if "чернобил" in text:
        errors.append("без сравнения с Чернобил")
    if not row.first_comment:
        errors.append("липсва първи коментар")
    # Липсващ YOUTUBE_URL не спира качването: коментарът чака линка (jobs._post_comment).
    return errors


def blocked_by_approval(row: Row) -> bool:
    return row.needs_approval and not row.approved
