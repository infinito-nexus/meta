import os
import pathlib
import subprocess
import time

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "docker_entrypoint" / "20-mig-git.sh"


def fake(bin_dir, name, body):
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def test_the_git_service_starts_only_once_a_fresh_clone_is_in_place(tmp_path):
    home = tmp_path / "mig"
    marker = tmp_path / "started"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake(bin_dir, "git", 'case "$1" in clone) sleep 1 ;; esac')
    fake(bin_dir, "python3", f'[ -d "{home}/mirror.git" ] && echo up > "{marker}" || echo down > "{marker}"')
    script = tmp_path / "entrypoint.sh"
    script.write_text(
        SCRIPT.read_text(encoding="utf-8").replace("/etc/nginx/mig-git.conf", str(tmp_path / "nginx.conf")),
        encoding="utf-8",
    )

    subprocess.run(
        ["sh", str(script)],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "MIG_GIT_ROOT": "owner/name",
             "MIG_GIT_HOME": str(home), "MIG_GIT_FORKS": "off", "MIG_GIT_PORT": "8399"},
        check=True,
    )
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)

    assert marker.read_text(encoding="utf-8").strip() == "up"
