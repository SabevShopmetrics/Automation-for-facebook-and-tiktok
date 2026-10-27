"""Минимален клиент за Facebook Graph API (Reels, видео, коментари)."""
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class GraphError(Exception):
    pass


class Graph:
    def __init__(self, page_id: str, token: str, version: str):
        self.page_id = page_id
        self.token = token
        self.base = f"https://graph.facebook.com/{version}"
        self.video_base = f"https://graph-video.facebook.com/{version}"

    def _call(self, method: str, url: str, params=None, body: bytes | None = None,
              headers=None, timeout: int = 120) -> dict:
        params = dict(params or {})
        if body is None and method == "POST":
            body = urllib.parse.urlencode({**params, "access_token": self.token}).encode()
            headers = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
        else:
            params["access_token"] = self.token
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                pass
            raise GraphError(f"{e.code}: {detail}") from None

    def whoami(self) -> dict:
        return self._call("GET", f"{self.base}/me", {"fields": "id,name"})

    def schedule_reel(self, path: Path, caption: str, publish_ts: int) -> str:
        start = self._call("POST", f"{self.base}/{self.page_id}/video_reels",
                           {"upload_phase": "start"})
        video_id = start["video_id"]
        upload_url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{self.base.rsplit('/', 1)[1]}/{video_id}"
        data = path.read_bytes()
        req = urllib.request.Request(upload_url, data=data, method="POST", headers={
            "Authorization": f"OAuth {self.token}",
            "offset": "0",
            "file_size": str(len(data)),
        })
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                result = json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            raise GraphError(f"качването на Reel върна {e.code}: {e.read().decode('utf-8', 'replace')}") from None
        if not result.get("success"):
            raise GraphError(f"качването на Reel не мина: {result}")
        finish = self._call("POST", f"{self.base}/{self.page_id}/video_reels", {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "SCHEDULED",
            "scheduled_publish_time": str(publish_ts),
            "description": caption,
        })
        if not finish.get("success", True):
            raise GraphError(f"насрочването на Reel не мина: {finish}")
        return video_id

    def schedule_feed_video(self, path: Path, caption: str, publish_ts: int) -> str:
        boundary = uuid.uuid4().hex
        fields = {
            "access_token": self.token,
            "description": caption,
            "published": "false",
            "scheduled_publish_time": str(publish_ts),
        }
        parts = []
        for name, value in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="source"; filename="{path.name}"\r\n'
                     f"Content-Type: video/mp4\r\n\r\n".encode())
        parts.append(path.read_bytes())
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)
        req = urllib.request.Request(f"{self.video_base}/{self.page_id}/videos", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                result = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise GraphError(f"качването на видео върна {e.code}: {e.read().decode('utf-8', 'replace')}") from None
        return result["id"]

    def video_status(self, video_id: str) -> dict:
        return self._call("GET", f"{self.base}/{video_id}", {"fields": "status,permalink_url"})

    def delete(self, object_id: str) -> bool:
        return bool(self._call("DELETE", f"{self.base}/{object_id}").get("success"))

    def comment(self, object_id: str, message: str) -> str:
        return self._call("POST", f"{self.base}/{object_id}/comments", {"message": message})["id"]


def is_published(status: dict) -> bool:
    """publish_status е draft, scheduled, published или error."""
    publishing = (status.get("status") or {}).get("publishing_phase") or {}
    return publishing.get("publish_status") == "published"
