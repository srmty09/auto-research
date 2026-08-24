import json
from pathlib import Path
from datetime import datetime

COSTS_PATH = Path(__file__).parent.parent / "workspace" / "costs.json"

# DeepSeek pricing (per 1M tokens)
MODEL_COSTS = {
    "deepseek-v4-flash": {
        "input": 0.27,
        "output": 1.10,
    },
    "deepseek-v4-pro": {
        "input": 0.54,
        "output": 2.19,
    },
}


def _load() -> dict:
    COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if COSTS_PATH.exists():
        try:
            return json.loads(COSTS_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"sessions": {}, "users": {}}


def _save(data: dict):
    COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    COSTS_PATH.write_text(json.dumps(data, indent=2))


def record_usage(
    session_id: str,
    user: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int = 0,
):
    """Record token usage for a session."""
    data = _load()
    
    # Calculate cost
    costs = MODEL_COSTS.get(model, MODEL_COSTS["deepseek-v4-flash"])
    cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
    
    # Session record
    if session_id not in data["sessions"]:
        data["sessions"][session_id] = {
            "user": user,
            "model": model,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "tool_calls": 0,
            "requests": 0,
            "created": datetime.now().isoformat(),
        }
    
    s = data["sessions"][session_id]
    s["total_input_tokens"] += input_tokens
    s["total_output_tokens"] += output_tokens
    s["total_cost"] = round(s["total_cost"] + cost, 6)
    s["tool_calls"] += tool_calls
    s["requests"] += 1
    s["model"] = model
    s["last_used"] = datetime.now().isoformat()
    
    # User totals
    if user not in data["users"]:
        data["users"][user] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "total_requests": 0,
            "sessions": 0,
        }
    
    u = data["users"][user]
    u["total_input_tokens"] += input_tokens
    u["total_output_tokens"] += output_tokens
    u["total_cost"] = round(u["total_cost"] + cost, 6)
    u["total_requests"] += 1
    if session_id not in [sid for sid in data["sessions"] if data["sessions"][sid].get("user") == user]:
        u["sessions"] += 1
    
    _save(data)


def get_session_usage(session_id: str) -> dict:
    """Get usage stats for a session."""
    data = _load()
    return data["sessions"].get(session_id, {})


def get_user_usage(user: str) -> dict:
    """Get total usage for a user."""
    data = _load()
    return data["users"].get(user, {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost": 0.0,
        "total_requests": 0,
        "sessions": 0,
    })


def format_cost(cost: float) -> str:
    """Format cost as readable string."""
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"


def format_tokens(tokens: int) -> str:
    """Format token count as readable string."""
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1_000_000:
        return f"{tokens/1000:.1f}K"
    else:
        return f"{tokens/1_000_000:.2f}M"
