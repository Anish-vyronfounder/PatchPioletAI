from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run_script(script_text: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    """Run a Python script in a temporary directory without using the server process."""
    with tempfile.TemporaryDirectory(prefix="patchpilot-") as tmpdir:
        script_path = Path(tmpdir) / "script.py"
        script_path.write_text(script_text, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONPATH"] = str(Path(tmpdir))

        process = subprocess.run(
            [sys.executable, "-I", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=tmpdir,
            env=env,
        )

        return {
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "timed_out": False,
        }
