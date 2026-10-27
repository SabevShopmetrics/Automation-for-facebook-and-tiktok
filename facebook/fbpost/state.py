"""Какво вече е направено, за да не се качва нищо два пъти."""
import json
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"posts": {}, "alerts": {}}
        if path.exists():
            self.data.update(json.loads(path.read_text(encoding="utf-8")))

    def post(self, row_id: str) -> dict:
        return self.data["posts"].setdefault(row_id, {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)
