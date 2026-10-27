"""TikTok инструмент за насрочване.

  python run.py serve    пуска страницата-инструмента и проверките на всеки 10 минути
  python run.py run      една проверка: сваля клиповете, праща напомняния и сигнали
  python run.py check    проверява целия график и файловете
"""
import sys

from tttool import config, jobs, server
from tttool.state import State


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:  # pythonw няма конзола
            stream.reconfigure(encoding="utf-8")
    command = argv[1] if len(argv) > 1 else "help"
    cfg = config.load()
    if command == "serve":
        server.serve(cfg)
        return 0
    if command == "run":
        jobs.Cycle(cfg, State(cfg.state_file)).run()
        return 0
    if command == "check":
        return 1 if jobs.check(cfg) else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
