"""Built-in sandboxed Python code executor.

Runs user-supplied code in a *separate subprocess* with resource limits
so that a misbehaving snippet cannot affect the host process.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from agentforge.tools.base import Tool

# Hard limits
_TIMEOUT_SECONDS = 30
_MAX_OUTPUT_BYTES = 50_000  # truncate output beyond this


async def _python_exec(code: str) -> str:
    """Execute Python code in an isolated subprocess and return stdout."""
    # Write code to a temp file so we don't have to escape shell args
    tmp = Path(tempfile.mktemp(suffix=".py"))
    try:
        # Prepend a tiny preamble that blocks dangerous imports at the
        # interpreter level.  Not bulletproof but raises the bar.
        preamble = textwrap.dedent("""\
            import builtins as _b
            _ALLOWED_MODULES = frozenset({
                "math", "statistics", "decimal", "fractions",
                "random", "string", "re", "json", "datetime",
                "collections", "itertools", "functools", "operator",
                "textwrap", "unicodedata", "enum", "dataclasses",
                "copy", "pprint", "typing", "abc", "io",
            })
            _real_import = _b.__import__
            def _safe_import(name, *a, **kw):
                top = name.split(".")[0]
                if top not in _ALLOWED_MODULES:
                    raise ImportError(f"Module '{name}' is not allowed")
                return _real_import(name, *a, **kw)
            _b.__import__ = _safe_import
        """)
        tmp.write_text(preamble + code, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", str(tmp),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={},  # empty env — no inherited secrets
        )

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Execution error: timed out after {_TIMEOUT_SECONDS}s"

        output = stdout.decode("utf-8", errors="replace")
        if len(output) > _MAX_OUTPUT_BYTES:
            output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated)"

        if proc.returncode != 0:
            return f"Execution error (exit {proc.returncode}):\n{output}"

        return output if output.strip() else "(no output)"

    except Exception as e:
        return f"Execution error: {type(e).__name__}: {e}"
    finally:
        tmp.unlink(missing_ok=True)


python_exec_tool = Tool(
    name="python_exec",
    description=(
        "Execute Python code in an isolated subprocess and return the output. "
        "Use for calculations, data processing, or generating content. "
        "Only safe standard-library modules are allowed (math, json, re, etc.)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
        },
        "required": ["code"],
    },
    handler=_python_exec,
)
