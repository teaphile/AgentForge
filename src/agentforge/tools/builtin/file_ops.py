"""Built-in file operation tools (read/write) with working-directory sandboxing."""

from __future__ import annotations

import os
from pathlib import Path

from agentforge.tools.base import Tool

def _sandbox_root() -> Path:
    """Evaluate at call time so env changes and test overrides take effect."""
    return Path(os.environ.get("AGENTFORGE_FILE_SANDBOX", ".")).resolve()


def _safe_path(path: str) -> Path:
    """Resolve path and ensure it stays within the sandbox root."""
    root = _sandbox_root()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError(f"Access denied: path escapes sandbox ({resolved})")
    return resolved


async def _file_read(path: str, max_lines: int = 500) -> str:
    try:
        file_path = _safe_path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        if len(lines) > max_lines:
            text = "\n".join(lines[:max_lines])
            text += f"\n\n... (truncated, {len(lines)} total lines)"
        return text
    except Exception as e:
        return f"Error reading file: {e}"


async def _file_write(path: str, content: str) -> str:
    try:
        file_path = _safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


file_read_tool = Tool(
    name="file_read",
    description="Read the contents of a local file. Returns the text content of the file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read (default: 500)",
                "default": 500,
            },
        },
        "required": ["path"],
    },
    handler=_file_read,
)


file_write_tool = Tool(
    name="file_write",
    description="Write content to a local file. Creates the file and any parent directories if they don't exist.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
    handler=_file_write,
)
