"""Подготовка на клиповете, напомняния и сигнали за пропуснати."""
from datetime import datetime, timedelta

from . import rules, schedule, sofia_time
from .config import Config
from .drive import Drive, DriveError
from .notify import Notifier
from .state import State

STUDIO_URL = "https://www.tiktok.com/tiktokstudio/upload"
URGENT = timedelta(hours=3)


def status_of(row: schedule.Row, state: State, now: datetime, window_days: int) -> str:
    if state.data["done"].get(row.id):
        return "done"
    if row.publish_at is None or rules.blocked_by_approval(row):
        return "waiting"
    if row.publish_at <= now:
        return "missed"
    if row.publish_at - now <= timedelta(days=window_days):
        return "now"
    return "later"


class Cycle:
    def __init__(self, cfg: Config, state: State):
        self.cfg = cfg
        self.state = state
        self.notify = Notifier(cfg, state)
        self.drive = Drive(cfg.drive_folder_id, cfg.drive_local_dir, cfg.cache_dir)
        self.last_run: datetime | None = None
        self.problems: dict[str, list[str]] = {}

    def load(self) -> list[schedule.Row]:
        return schedule.load(self.cfg.schedule_csv, self.cfg.schedule_csv_url)

    def prepare(self, row: schedule.Row) -> list[str]:
        errors = rules.check(row, self.cfg.premiere_at)
        try:
            self.drive.fetch(row.drive_path)
        except (DriveError, OSError) as e:
            errors.append(f"файлът не се взима от Drive: {e}")
        return errors

    def local_file(self, row: schedule.Row):
        if self.cfg.drive_local_dir:
            p = self.drive.local_dir / row.drive_path
        else:
            p = self.cfg.cache_dir / row.drive_path
        return p if p.is_file() else None

    def run(self, now: datetime | None = None) -> None:
        now = now or sofia_time.now_utc()
        try:
            rows = self.load()
        except (OSError, ValueError) as e:
            self.notify.alert("schedule", "Графикът не се чете", str(e))
            self.state.save()
            return
        self.notify.clear("schedule")
        self.last_run = now
        new_ready = []
        for row in rows:
            status = status_of(row, self.state, now, self.cfg.window_days)
            if status == "missed" and now - row.publish_at < timedelta(hours=24):
                self.notify.alert(f"missed:{row.id}", f"Клип {row.id} не е насрочен",
                                  f"Часът {row.publish_at_text} мина, а клипът не е отбелязан като насрочен в TikTok.\n{self.cfg.tool_url}")
            if status != "now":
                continue
            errors = self.prepare(row)
            self.problems[row.id] = errors
            if errors:
                self.notify.alert(f"invalid:{row.id}", f"Клип {row.id} има проблем",
                                  f"{row.publish_at_text} · {row.drive_path}\n- " + "\n- ".join(errors))
                continue
            self.notify.clear(f"invalid:{row.id}")
            if not self.state.data["reminded"].get(row.id):
                new_ready.append(row)
            elif row.publish_at - now < URGENT:
                self.notify.alert(f"urgent:{row.id}", f"Спешно: клип {row.id} още не е насрочен",
                                  f"Трябва да излезе в {row.publish_at_text}.\n{self.cfg.tool_url}")
        if new_ready:
            lines = "\n".join(f"- {r.publish_at_text}  клип {r.id}" for r in new_ready)
            self.notify.email(f"{len(new_ready)} клипа за насрочване в TikTok",
                              f"Тези клипове вече могат да се насрочат в TikTok Studio:\n{lines}\n\n"
                              f"Отворете инструмента: {self.cfg.tool_url}")
            for r in new_ready:
                self.state.data["reminded"][r.id] = sofia_time.to_local(now)
        self.state.save()


def check(cfg: Config) -> int:
    state = State(cfg.state_file)
    cycle = Cycle(cfg, state)
    problems = 0
    for row in cycle.load():
        if rules.blocked_by_approval(row):
            print(f"ЧАКА  {row.id:<8} {row.publish_at_text or '(без дата)':<17} чака одобрение")
            continue
        errors = cycle.prepare(row)
        if errors:
            problems += 1
            print(f"ГРЕШКА {row.id:<7} {row.publish_at_text:<17} " + "; ".join(errors))
        else:
            print(f"ОК    {row.id:<8} {row.publish_at_text:<17} {row.drive_path}")
    return problems
