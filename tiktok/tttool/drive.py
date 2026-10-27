"""Взимане на файлове от Google Drive.

Два режима:
- DRIVE_LOCAL_DIR: папката е синхронизирана локално (Google Drive for Desktop).
- DRIVE_FOLDER_ID: публична папка ("всеки с линка"), четена без ключ.
"""
import html
import re
import shutil
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (tiktok-autopost)"
_PAIR = re.compile(r'data-id="([A-Za-z0-9_-]{20,})"[^>]*?data-tooltip="([^"]+)"')


class DriveError(Exception):
    pass


def _get(url: str, timeout: int = 120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


class Drive:
    def __init__(self, folder_id: str, local_dir: str, cache_dir: Path):
        self.folder_id = folder_id
        self.local_dir = Path(local_dir) if local_dir else None
        self.cache_dir = cache_dir
        self._listings: dict[str, list[tuple[str, str]]] = {}

    def fetch(self, rel_path: str) -> Path:
        """Връща локален път до файла; при нужда го сваля в кеша."""
        rel_path = rel_path.strip().strip("/")
        if self.local_dir:
            p = self.local_dir / rel_path
            if not p.is_file():
                raise DriveError(f"Няма файл в синхронизираната папка: {p}")
            return p
        if not self.folder_id:
            raise DriveError("Не е зададено DRIVE_FOLDER_ID или DRIVE_LOCAL_DIR")
        target = self.cache_dir / rel_path
        if target.is_file() and target.stat().st_size > 0:
            return target
        file_id = self._resolve(rel_path)
        self._download(file_id, target)
        return target

    def _children(self, folder_id: str) -> list[tuple[str, str]]:
        if folder_id not in self._listings:
            with _get(f"https://drive.google.com/drive/folders/{folder_id}") as r:
                page = r.read().decode("utf-8", "replace")
            seen, items = set(), []
            for m in _PAIR.finditer(page):
                fid, tip = m.group(1), html.unescape(m.group(2))
                if fid != folder_id and fid not in seen:
                    seen.add(fid)
                    items.append((fid, tip))
            if not items:
                raise DriveError(f"Папката {folder_id} е празна или не е публична")
            self._listings[folder_id] = items
        return self._listings[folder_id]

    def _resolve(self, rel_path: str) -> str:
        current = self.folder_id
        for part in rel_path.split("/"):
            match = [fid for fid, tip in self._children(current)
                     if tip == part or tip.startswith(part + " ")]
            if not match:
                raise DriveError(f"Няма '{part}' в Drive (път: {rel_path})")
            current = match[0]
        return current

    def _download(self, file_id: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
        with _get(url, timeout=600) as r:
            if "text/html" in (r.headers.get("Content-Type") or ""):
                raise DriveError(f"Drive върна страница вместо файл (id {file_id}). Папката публична ли е?")
            with open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
        tmp.replace(target)
