import subprocess
import sys
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

from langchain_core.tools import tool


WORKSPACE_DIR = Path(__file__).parent.parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


def _search_exa(query: str, num_results: int = 5) -> str | None:
    """Primary search via Exa (semantic search with content extraction)."""
    from .config import EXA_API_KEY
    if not EXA_API_KEY:
        return None
    try:
        from exa_py import Exa
        exa = Exa(api_key=EXA_API_KEY)
        results = exa.search(
            query,
            num_results=num_results,
            type="neural",
        )
        if not results.results:
            return None
        formatted = []
        for r in results.results:
            content = (r.text or r.highlight or "")[:1500]
            formatted.append(
                f"Title: {r.title}\n"
                f"URL: {r.url}\n"
                f"Content: {content}\n"
            )
        return "\n---\n".join(formatted)
    except Exception:
        return None


def _search_duckduckgo(query: str, max_results: int = 5) -> str | None:
    """Fallback search via DuckDuckGo (with threading timeout)."""
    import threading

    result_holder = [None]
    error_holder = [None]

    def _do_search():
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if results:
                formatted = []
                for r in results:
                    formatted.append(
                        f"Title: {r.get('title', 'N/A')}\n"
                        f"Snippet: {r.get('body', 'N/A')}\n"
                        f"URL: {r.get('href', 'N/A')}\n"
                    )
                result_holder[0] = "\n---\n".join(formatted)
        except Exception as e:
            error_holder[0] = e

    t = threading.Thread(target=_do_search, daemon=True)
    t.start()
    t.join(timeout=8)
    if t.is_alive():
        return None  # timed out
    return result_holder[0]


def _search_brave_fallback(query: str, num_results: int = 5) -> str | None:
    """Fallback: use Brave Search API via httpx (free tier: 2000 queries/mo)."""
    # Only works if BRAVE_API_KEY is set
    from .config import BRAVE_API_KEY
    if not BRAVE_API_KEY:
        return None
    try:
        import httpx
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": num_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        web_results = data.get("web", {}).get("results", [])
        if not web_results:
            return None
        formatted = []
        for r in web_results:
            formatted.append(
                f"Title: {r.get('title', 'N/A')}\n"
                f"Snippet: {r.get('description', 'N/A')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
            )
        return "\n---\n".join(formatted)
    except Exception:
        return None


@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic.
    Search order: Exa (semantic) → DuckDuckGo → Brave Search."""
    # 1. Try Exa first (best quality, semantic search)
    result = _search_exa(query)
    if result:
        return result

    # 2. Try DuckDuckGo (free, no API key needed)
    result = _search_duckduckgo(query)
    if result:
        return f"[via DuckDuckGo]\n{result}"

    # 3. Try Brave Search (if API key is set)
    result = _search_brave_fallback(query)
    if result:
        return f"[via Brave Search]\n{result}"

    return "No search results found. All search backends failed or are unavailable."


@tool
def web_fetch(url: str) -> str:
    """Fetch and extract readable text content from a specific URL."""
    if not url:
        return "No URL provided."
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AutoResearchAgent/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        text = "\n".join(lines)
        if len(text) > 8000:
            text = text[:8000] + "\n\n[truncated...]"
        return text or "(empty page)"
    except urllib.error.HTTPError as e:
        return f"HTTP error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"URL error: {e.reason}"
    except Exception as e:
        return f"Failed to fetch URL: {e}"


def _get_python_repl():
    """Get a LangChain PythonREPLTool instance."""
    from langchain_experimental.tools.python.tool import PythonREPLTool
    return PythonREPLTool()


# Module-level tool instance for the agent
_execute_code_tool = None

def execute_code(code: str) -> str:
    """Execute Python code for calculations or data processing.
    Uses LangChain's PythonREPLTool which runs code in a subprocess."""
    global _execute_code_tool
    if _execute_code_tool is None:
        _execute_code_tool = _get_python_repl()
    try:
        result = _execute_code_tool.invoke({"query": code})
        return str(result) if result else "(no output)"
    except Exception as e:
        err = str(e)
        # Filter common noise
        err_lines = [l for l in err.split("\n") if l.strip() and "warning" not in l.lower()]
        return "Error: " + "\n".join(err_lines[-5:]) if err_lines else f"Error: {e}"


def make_save_file(user_id=None, session_id=None):
    @tool
    def save_file(filepath: str, content: str) -> str:
        """Save content to a file in the workspace."""
        if not filepath:
            return "No filepath provided."
        target = WORKSPACE_DIR / filepath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        # Index into shared collection for future search
        try:
            from .vector_store import add_document
            add_document(content, metadata={"title": filepath, "source": "file"})
        except Exception:
            pass
        # Also save to session memory if session is active
        if session_id:
            try:
                from .vector_store import add_session_memory
                add_session_memory(session_id, content, goal=filepath)
            except Exception:
                pass
        return f"Wrote {len(content)} bytes to {filepath}"

    return save_file


def make_read_file(user_id=None):
    @tool
    def read_file(filepath: str) -> str:
        """Read content from a file in the workspace."""
        if not filepath:
            return "No filepath provided."
        target = WORKSPACE_DIR / filepath
        if not target.exists():
            return f"File not found: {filepath}"
        content = target.read_text(errors="replace")
        if len(content) > 10000:
            content = content[:10000] + "\n\n[truncated...]"
        return content

    return read_file


def make_list_files(user_id=None):
    @tool
    def list_files() -> str:
        """List all files in the workspace directory."""
        files = []
        for f in sorted(WORKSPACE_DIR.rglob("*")):
            if f.is_file() and f.name not in ("sessions.json", "users.json"):
                rel = f.relative_to(WORKSPACE_DIR)
                files.append(f"{rel} ({f.stat().st_size} bytes)")
        if not files:
            return "No files found."
        return "\n".join(files)

    return list_files


@tool
def get_session_history() -> str:
    """View recent past sessions (goals, success status, steps, time)."""
    try:
        from .session_store import SessionStore
        store = SessionStore()
        sessions = store.list_sessions(limit=10)
        if not sessions:
            return "No past sessions found."
        lines = ["Past sessions (most recent first):"]
        for s in sessions:
            status = "SUCCESS" if s["success"] else "FAILED"
            lines.append(
                f"  [{status}] {s['id']} | goal: {s['goal'][:60]} | "
                f"steps: {s['steps']} | time: {s['time']}s"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to read session history: {e}"


def make_vector_search(session_id=None):
    @tool
    def vector_search(query: str) -> str:
        """Search past research and saved documents using semantic similarity.
        If a session is active, searches both that session's memory AND shared docs.
        Otherwise searches only shared docs (uploaded files, saved reports)."""
        try:
            from .vector_store import search
            results = search(query, k=5, session_id=session_id)
            if not results:
                return "No relevant documents found in the knowledge base."
            lines = [f"Found {len(results)} relevant results:"]
            for i, r in enumerate(results, 1):
                src = r.get("source", "unknown")
                lines.append(
                    f"\n--- Result {i} (similarity: {r['score']:.2f}, source: {src}) ---\n"
                    f"{r['content'][:500]}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Vector search failed: {e}"

    return vector_search


def get_all_tools(user_id=None, session_id=None):
    """Return all LangChain tools for the agent, with user-scoped file tools."""
    python_tool = _get_python_repl()
    return [
        web_search,
        web_fetch,
        python_tool,
        make_vector_search(session_id),
        make_save_file(user_id, session_id),
        make_read_file(user_id),
        make_list_files(user_id),
        get_session_history,
    ]
