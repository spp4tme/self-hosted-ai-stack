"""Tests du sandbox d'exécution."""

import pytest
from agents.constitutional import ConstitutionalMiddleware


def test_dangerous_imports_detection():
    from sandbox.executor import check_dangerous_imports

    safe_code = "import math\nprint(math.pi)"
    danger_code = "import subprocess\nsubprocess.run(['ls'])"
    assert check_dangerous_imports(safe_code)   == []
    assert "subprocess" in check_dangerous_imports(danger_code)


def test_dangerous_imports_from():
    from sandbox.executor import check_dangerous_imports
    code = "from os import path\npath.exists('/')"
    assert "os" in check_dangerous_imports(code)


def test_detect_packages():
    from sandbox.executor import _detect_packages
    code = "import numpy as np\nimport pandas as pd\nimport math"
    pkgs = _detect_packages(code)
    assert "numpy"  in pkgs
    assert "pandas" in pkgs
    assert "math"   not in pkgs   # stdlib


def test_sandbox_blocks_dangerous_code():
    from sandbox.executor import SandboxExecutor, check_dangerous_imports
    danger_code = "import subprocess; subprocess.run(['whoami'])"
    blocked = check_dangerous_imports(danger_code)
    assert len(blocked) > 0


def test_execution_result_fields():
    from sandbox.executor import ExecutionResult
    r = ExecutionResult(
        success=True,
        stdout="hello",
        stderr="",
        duration_s=0.5,
        blocked=[],
    )
    assert r.success
    assert r.stdout == "hello"
