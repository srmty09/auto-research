import subprocess
import sys
import os
import re
import urllib.request
import urllib.error
from pathlib import Path


class WebFetchTool:
    def execute(self, url: str) -> str:
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


class WebSearchTool:
    def execute(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                formatted.append(
                    f"Title: {r.get('title', 'N/A')}\n"
                    f"Snippet: {r.get('body', 'N/A')}\n"
                    f"URL: {r.get('href', 'N/A')}\n"
                )
            return "\n---\n".join(formatted)
        except ImportError:
            return "DuckDuckGo search not available. Install with: pip install duckduckgo_search"
        except Exception as e:
            return f"Search failed: {e}"


class CodeExecutionTool:
    def execute(self, code: str) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "Execution timed out after 30s"
        except Exception as e:
            return f"Execution error: {e}"


class FileTool:
    def __init__(self):
        self.workspace = Path(os.path.join(os.path.dirname(__file__), "..", "workspace"))
        self.workspace.mkdir(exist_ok=True)

    def read(self, filepath: str) -> str:
        if not filepath:
            return "No filepath provided."
        path = self.workspace / filepath
        if not path.exists():
            return f"File not found: {filepath}"
        return path.read_text()

    def write(self, filepath: str, content: str) -> str:
        if not filepath:
            return "No filepath provided."
        path = self.workspace / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Wrote {len(content)} bytes to {filepath}"

    def list_files(self) -> str:
        files = list(self.workspace.iterdir())
        if not files:
            return "Workspace is empty."
        lines = []
        for f in sorted(files):
            size = f.stat().st_size
            lines.append(f"{f.name} ({size} bytes)")
        return "\n".join(lines)


class SessionHistoryTool:
    def execute(self) -> str:
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


class ToolRegistry:
    def __init__(self):
        self.search = WebSearchTool()
        self.fetch = WebFetchTool()
        self.code = CodeExecutionTool()
        self.file = FileTool()
        self.sessions = SessionHistoryTool()

    def definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information on any topic",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Fetch and extract readable text content from a specific URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The full URL to fetch (e.g. https://example.com/page)",
                            }
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": "Execute Python code for calculations or data processing",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Valid Python code to run",
                            }
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_file",
                    "description": "Save content to a file in the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "Relative file path (e.g. report.md)",
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write",
                            },
                        },
                        "required": ["filepath", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read content from a file in the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "Relative file path to read",
                            }
                        },
                        "required": ["filepath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List all files in the workspace directory",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_session_history",
                    "description": "View recent past sessions (goals, success status, steps, time)",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
        ]

    def execute(self, name: str, args: dict) -> str:
        if name == "web_search":
            return self.search.execute(args.get("query", ""))
        elif name == "web_fetch":
            return self.fetch.execute(args.get("url", ""))
        elif name == "execute_code":
            return self.code.execute(args.get("code", ""))
        elif name == "save_file":
            return self.file.write(
                args.get("filepath", "output.txt"),
                args.get("content", ""),
            )
        elif name == "read_file":
            return self.file.read(args.get("filepath", ""))
        elif name == "list_files":
            return self.file.list_files()
        elif name == "get_session_history":
            return self.sessions.execute()
        return f"Unknown tool: {name}"
