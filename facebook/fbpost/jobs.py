"""Работата на всяко пускане: насрочване на качванията и първите коментари."""
from datetime import datetime, timedelta

from . import mp4, rules, schedule, sofia_time
from .config import Config
from .drive import Drive, DriveError
from .graph import Graph, GraphError, is_published
from .notify import Notifier
from .state import State

DAILY_LIMIT = 25  # Meta позволява 30 публикации през API за 24 часа


def _comment_text(row: schedule.Row, cfg: Config) -> str:
    return row.first_comment.replace("{youtube_url}", cfg.youtube_url)


def _validate(row, cfg, drive) -> tuple[list[str], object]:
    errors = rules.check(row, cfg.premiere_at, cfg.youtube_url)
    path = None
    try:
        path = drive.fetch(row.drive_path)
    except (DriveError, OSError) as e:
        errors.append(f"файлът не се взима от Drive: {e}")
    if path and row.type == "reel":
        seconds = mp4.duration_seconds(path)
        if seconds and seconds > rules.REEL_MAX_SECONDS:
            errors.append(f"клипът е {seconds:.0f} сек., Reel може до {rules.REEL_MAX_SECONDS} сек. (сменете типа на feed_video)")
    return errors, path


class Runner:
    def __init__(self, cfg: Config, now: datetime | None = None):
        self.cfg = cfg
        self.now = now or sofia_time.now_utc()
        self.state = State(cfg.state_file)
        self.notify = Notifier(cfg, self.state)
        self.drive = Drive(cfg.drive_folder_id, cfg.drive_local_dir, cfg.cache_dir)
        self.dry = cfg.dry_run or not cfg.page_token
        self.graph = Graph(cfg.page_id, cfg.page_token, cfg.graph_version) if cfg.page_token else None

    def run(self, only: set[str] | None = None) -> None:
        """Едно пускане. Ако друго пускане още върви, това спира веднага."""
        lock = self.cfg.state_file.with_name("run.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists() and datetime.now().timestamp() - lock.stat().st_mtime < 3 * 3600:
            self.notify.log("Друго пускане още върви, това спира.")
            return
        lock.write_text(sofia_time.to_local(self.now), encoding="utf-8")
        try:
            self._run(only)
        finally:
            lock.unlink(missing_ok=True)

    def _run(self, only: set[str] | None) -> None:
        try:
            rows = schedule.load(self.cfg.schedule_csv, self.cfg.schedule_csv_url)
        except (OSError, ValueError) as e:
            self.notify.alert("schedule", "Графикът не се чете", str(e))
            self.state.save()
            return
        self.notify.clear("schedule")
        if only:
            rows = [r for r in rows if r.id in only]
        if self.dry:
            self.notify.log("Пробен режим: нищо не се публикува (DRY_RUN=1 или няма ключ).")
        elif not self._token_ok():
            self.state.save()
            return
        for row in rows:
            self._schedule_upload(row, rows)
            self._post_comment(row)
        self.state.save()

    def _token_ok(self) -> bool:
        try:
            me = self.graph.whoami()
        except (GraphError, OSError) as e:
            self.notify.alert("token", "Ключът за страницата не работи",
                              f"{e}\nПоискайте нов ключ по документа „Facebook: ключ за страницата“.")
            return False
        if self.cfg.page_id and me.get("id") != self.cfg.page_id:
            self.notify.alert("token", "Ключът е за друга страница",
                              f"Ключът е за {me.get('name')} ({me.get('id')}), а FB_PAGE_ID е {self.cfg.page_id}.")
            return False
        self.notify.clear("token")
        return True

    def _schedule_upload(self, row, rows) -> None:
        post = self.state.post(row.id)
        if post.get("video_id") or post.get("cancelled") or row.publish_at is None:
            return
        if rules.blocked_by_approval(row):
            if row.publish_at - self.now < timedelta(days=2):
                self.notify.alert(f"approval:{row.id}", f"{row.id} чака одобрение",
                                  f"Публикацията {row.id} ({row.publish_at_text}) е спряна, докато в графика "
                                  f"не се отбележи approved = да.")
            return
        lead = row.publish_at - self.now
        if lead > timedelta(days=self.cfg.upload_window_days):
            return
        if lead < timedelta(minutes=self.cfg.min_lead_minutes):
            if lead > timedelta(hours=-24):
                self.notify.alert(f"missed:{row.id}", f"{row.id} не е насрочена навреме",
                                  f"Часът {row.publish_at_text} е твърде близо или е минал, а публикацията не е качена.")
            return
        errors, path = _validate(row, self.cfg, self.drive)
        same_day = [r for r in rows if r.publish_at and abs(r.publish_at - row.publish_at) < timedelta(hours=24)
                    and self.state.post(r.id).get("video_id")]
        if len(same_day) >= DAILY_LIMIT:
            errors.append(f"над {DAILY_LIMIT} публикации за 24 часа")
        if errors:
            self.notify.alert(f"invalid:{row.id}", f"{row.id} е спряна",
                              f"{row.publish_at_text} · {row.drive_path}\n- " + "\n- ".join(errors))
            return
        self.notify.clear(f"invalid:{row.id}")
        ts = int(row.publish_at.timestamp())
        if self.dry:
            self.notify.log(f"[проба] {row.id}: щеше да насрочи {row.type} за {row.publish_at_text} ({path.name})")
            return
        try:
            if row.type == "reel":
                video_id = self.graph.schedule_reel(path, row.caption, ts)
            else:
                video_id = self.graph.schedule_feed_video(path, row.caption, ts)
        except (GraphError, OSError) as e:
            self.notify.alert(f"upload:{row.id}", f"{row.id} не се качи", str(e))
            return
        self.notify.clear(f"upload:{row.id}")
        post.update(video_id=video_id, type=row.type, scheduled_for=row.publish_at_text,
                    uploaded_at=sofia_time.to_local(self.now))
        self.state.save()
        self.notify.log(f"{row.id}: насрочено за {row.publish_at_text} (видео {video_id})")

    def _post_comment(self, row) -> None:
        post = self.state.post(row.id)
        if not post.get("video_id") or post.get("comment_id") or row.publish_at is None:
            return
        if self.now < row.publish_at:
            return
        late = self.now > row.publish_at + timedelta(minutes=self.cfg.comment_grace_minutes)
        if self.dry:
            return
        if "{youtube_url}" in row.first_comment and not self.cfg.youtube_url:
            self.notify.alert("youtube_url", "Липсва линкът към YouTube",
                              f"{row.id} излезе, но коментарът с линка чака. Попълнете YOUTUBE_URL в .env, "
                              f"скриптът ще пусне коментарите сам.")
            return
        try:
            status = self.graph.video_status(post["video_id"])
            if not is_published(status):
                if late:
                    self.notify.alert(f"notlive:{row.id}", f"{row.id} не е излязла",
                                      f"Насрочена за {row.publish_at_text}, но Facebook още не я показва. Статус: {status.get('status')}")
                return
            comment_id = self.graph.comment(post["video_id"], _comment_text(row, self.cfg))
        except (GraphError, OSError) as e:
            if late:
                self.notify.alert(f"comment:{row.id}", f"{row.id}: коментарът не се пусна", str(e))
            return
        self.notify.clear(f"notlive:{row.id}")
        self.notify.clear(f"comment:{row.id}")
        post.update(comment_id=comment_id, permalink=status.get("permalink_url", ""),
                    commented_at=sofia_time.to_local(self.now))
        self.state.save()
        self.notify.log(f"{row.id}: излезе, коментарът с линка е пуснат")


def check(cfg: Config) -> int:
    """Проверява целия график и всички файлове, без да публикува. Връща броя проблеми."""
    rows = schedule.load(cfg.schedule_csv, cfg.schedule_csv_url)
    drive = Drive(cfg.drive_folder_id, cfg.drive_local_dir, cfg.cache_dir)
    problems = 0
    for row in rows:
        if rules.blocked_by_approval(row):
            print(f"ЧАКА  {row.id:<8} {row.publish_at_text or '(без дата)':<17} чака одобрение")
            continue
        errors, path = _validate(row, cfg, drive)
        seconds = mp4.duration_seconds(path) if path else None
        length = f"{seconds:.1f} сек." if seconds else "?"
        if errors:
            problems += 1
            print(f"ГРЕШКА {row.id:<7} {row.publish_at_text:<17} {row.type:<10} " + "; ".join(errors))
        else:
            print(f"ОК    {row.id:<8} {row.publish_at_text:<17} {row.type:<10} {length:<10} {row.drive_path}")
    if not cfg.youtube_url:
        print("ВНИМАНИЕ: YOUTUBE_URL не е зададен. Без него коментарите с линка няма да тръгнат.")
    if not cfg.page_token:
        print("ВНИМАНИЕ: няма FB_PAGE_TOKEN. Работи само в пробен режим.")
    return problems
