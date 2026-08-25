import json
import bcrypt
from pathlib import Path

STORE_PATH = Path(__file__).parent.parent / "workspace" / "users.json"


def _load() -> dict:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2))


def register(username: str, password: str) -> dict | None:
    users = _load()
    if username in users:
        return None
    users[username] = {
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "profile": {
            "name": "",
            "role": "",
            "research_interests": [],
            "preferences": {
                "detail_level": "balanced",
                "output_format": "markdown",
            },
        },
    }
    _save(users)
    return {"username": username}


def login(username: str, password: str) -> dict | None:
    users = _load()
    user = users.get(username)
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return None
    if "profile" not in user:
        user["profile"] = {
            "name": "",
            "role": "",
            "research_interests": [],
            "preferences": {
                "detail_level": "balanced",
                "output_format": "markdown",
            },
        }
        _save(users)
    return {"username": username, "profile": user["profile"]}


def get_profile(username: str) -> dict:
    users = _load()
    user = users.get(username, {})
    return user.get("profile", {
        "name": "",
        "role": "",
        "research_interests": [],
        "preferences": {"detail_level": "balanced", "output_format": "markdown"},
    })


def update_profile(username: str, profile: dict) -> bool:
    users = _load()
    if username not in users:
        return False
    users[username]["profile"] = profile
    _save(users)
    return True


def get_user_context(username: str) -> str:
    """Build a context string from the user's profile for the agent system prompt."""
    profile = get_profile(username)
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("role"):
        parts.append(f"Role: {profile['role']}")
    interests = profile.get("research_interests", [])
    if interests:
        parts.append(f"Interests: {', '.join(interests)}")
    prefs = profile.get("preferences", {})
    if prefs.get("detail_level"):
        parts.append(f"Detail level: {prefs['detail_level']}")
    if prefs.get("output_format"):
        parts.append(f"Preferred output: {prefs['output_format']}")
    return " | ".join(parts) if parts else ""
