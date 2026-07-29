import json
import os
from pathlib import Path
from datetime import datetime


class SessionStore:
    def __init__(self):
        self.store_dir = Path(os.path.join(os.path.dirname(__file__), "..", "workspace"))
        self.store_dir.mkdir(exist_ok=True)
        self.store_path = self.store_dir / "sessions.json"
        self._sessions = None

    def _load(self):
        if self._sessions is not None:
            return
        if self.store_path.exists():
            try:
                self._sessions = json.loads(self.store_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._sessions = []
        else:
            self._sessions = []

    def _save(self):
        self.store_path.write_text(json.dumps(self._sessions, indent=2))

    def add_session(self, session_data: dict, user: str = ""):
        self._load()
        session_data["id"] = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        session_data["user"] = user
        self._sessions.append(session_data)
        self._save()
        return session_data["id"]

    def get_session(self, session_id: str) -> dict | None:
        self._load()
        for s in self._sessions:
            if s["id"] == session_id:
                return s
        return None

    def list_sessions(self, limit: int = 50, user: str = "") -> list[dict]:
        self._load()
        filtered = self._sessions
        if user:
            filtered = [s for s in filtered if s.get("user") == user]
        return [
            {
                "id": s["id"],
                "goal": s["goal"],
                "success": s["success"],
                "steps": s["steps"],
                "time": s["time"],
                "timestamp": s["timestamp"],
                "user": s.get("user", ""),
            }
            for s in reversed(filtered[-limit:])
        ]

    def delete_session(self, session_id: str):
        self._load()
        self._sessions = [s for s in self._sessions if s["id"] != session_id]
        self._save()

    def clear_all(self):
        self._sessions = []
        self._save()
