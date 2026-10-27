"""Кои клипове са насрочени в TikTok и кои напомняния са пратени."""
import json
import threading
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"done": {}, "reminded": {}, "alerts": {}}
        if path.exists():
            self.data.update(json.loads(path.read_text(encoding="utf-8")))

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
