"""Facebook автопостинг.

  python run.py check    проверява графика и файловете, без да публикува
  python run.py run      едно пускане: насрочва качванията и пуска коментарите
  python run.py run T1   само за посочените публикации (за проба)
  python run.py status   какво е насрочено и какво е излязло
  python run.py token    проверява ключа за страницата
  python run.py manual T1   отбелязва поста като пуснат на ръка (скриптът го прескача)
  python run.py cancel T2   трие насрочен пост от Facebook и го спира (или: cancel all)
  python run.py resume T2   пуска спрян пост отново
"""
import sys

from fbpost import config, jobs, schedule, sofia_time
from fbpost.graph import Graph, GraphError
from fbpost.state import State


def cancel(cfg, command: str, targets: list[str]) -> int:
    """cancel: трие от Facebook насрочените, още неизлезли постове и ги спира.
    resume: пуска спрените отново (качват се при следващото пускане)."""
    if not targets:
        print(f"Посочете id или all, напр.: python run.py {command} T2")
        return 1
    if cfg.state_file.with_name("run.lock").exists():
        print("В момента върви пускане. Изчакайте да свърши и опитайте пак.")
        return 1
    rows = {r.id: r for r in schedule.load(cfg.schedule_csv, cfg.schedule_csv_url)}
    state = State(cfg.state_file)
    posts = state.data["posts"]
    ids = list(rows) if targets == ["all"] else targets
    unknown = [i for i in ids if i not in rows]
    if unknown:
        print(f"Няма такива id в графика: {', '.join(unknown)}")
        return 1
    now = sofia_time.now_utc()
    graph = Graph(cfg.page_id, cfg.page_token, cfg.graph_version)
    for row_id in ids:
        post = posts.get(row_id, {})
        if command == "resume":
            if post.get("cancelled"):
                posts.pop(row_id)
                print(f"{row_id}: пуснат отново, ще се качи при следващото пускане")
            continue
        if post.get("manual") or post.get("cancelled"):
            continue
        if not post.get("video_id"):
            posts[row_id] = {"cancelled": True}
            print(f"{row_id}: спрян, няма да се качва")
            continue
        if rows[row_id].publish_at and rows[row_id].publish_at <= now:
            print(f"{row_id}: вече е излязъл. Махнете го ръчно от Meta Business Suite, ако трябва.")
            continue
        try:
            graph.delete(post["video_id"])
        except (GraphError, OSError) as e:
            print(f"{row_id}: не се изтри от Facebook: {e}")
            continue
        posts[row_id] = {"cancelled": True, "deleted_video": post["video_id"]}
        print(f"{row_id}: изтрит от Facebook и спрян")
    state.save()
    return 0


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:  # pythonw няма конзола
            stream.reconfigure(encoding="utf-8")
    command = argv[1] if len(argv) > 1 else "help"
    cfg = config.load()
    if command == "check":
        return 1 if jobs.check(cfg) else 0
    if command == "run":
        jobs.Runner(cfg).run(set(argv[2:]) or None)
        return 0
    if command == "status":
        state = State(cfg.state_file)
        for row in schedule.load(cfg.schedule_csv, cfg.schedule_csv_url):
            post = state.data["posts"].get(row.id, {})
            if post.get("cancelled"):
                mark = "спрян"
            elif post.get("manual"):
                mark = "на ръка"
            elif post.get("comment_id"):
                mark = "излязла"
            elif post.get("video_id"):
                mark = "насрочена"
            else:
                mark = "предстои"
            print(f"{row.id:<8} {row.publish_at_text or '(без дата)':<17} {mark:<10} {post.get('permalink', '')}")
        return 0
    if command == "token":
        if not cfg.page_token:
            print("Няма FB_PAGE_TOKEN в .env")
            return 1
        try:
            me = Graph(cfg.page_id, cfg.page_token, cfg.graph_version).whoami()
        except (GraphError, OSError) as e:
            print(f"Ключът не работи: {e}")
            return 1
        ok = me.get("id") == cfg.page_id
        print(f"Ключът е за: {me.get('name')} ({me.get('id')}) {'— съвпада с FB_PAGE_ID' if ok else '— НЕ съвпада с FB_PAGE_ID'}")
        return 0 if ok else 1
    if command == "manual":
        ids = {r.id for r in schedule.load(cfg.schedule_csv, cfg.schedule_csv_url)}
        unknown = [i for i in argv[2:] if i not in ids]
        if not argv[2:] or unknown:
            print(f"Посочете съществуващи id от графика. Непознати: {', '.join(unknown) or '(няма посочени)'}")
            return 1
        state = State(cfg.state_file)
        for row_id in argv[2:]:
            state.post(row_id).update(manual=True, video_id="manual", comment_id="manual",
                                      marked_at=sofia_time.to_local(sofia_time.now_utc()))
            print(f"{row_id}: отбелязан като пуснат на ръка")
        state.save()
        return 0
    if command in ("cancel", "resume"):
        return cancel(cfg, command, argv[2:])
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
