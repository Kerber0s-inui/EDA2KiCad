from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_repo_root_python_process_can_import_src_package() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import eda2kicad.web.app as app_module; "
                "print(app_module.app.title)"
            ),
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "eda2kicad local web"
