import os
import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "mtu.sh"


def fake(bin_dir, name, body):
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def run(tmp_path, env_text, automtu=None, bridge=None, module=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake(bin_dir, "automtu", f'echo {automtu}' if automtu else "exit 1")
    fake(bin_dir, "docker", f'echo {bridge}' if bridge else "exit 1")
    # Answers only the automtu module, so reaching for another one fails.
    fake(bin_dir, "python",
         f'case "$*" in "-m automtu "*) echo {module} ;; *) exit 1 ;; esac'
         if module else "exit 1")

    env_file = tmp_path / "env"
    env_file.write_text(env_text, encoding="utf-8")
    done = subprocess.run(
        ["sh", str(SCRIPT), str(env_file)],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "PYTHON": str(bin_dir / "python")},
        capture_output=True, text=True, check=True,
    )
    return env_file.read_text(encoding="utf-8"), done.stdout


def test_the_probed_value_wins_over_every_fallback(tmp_path):
    written, said = run(tmp_path, "MIG_PORT=8000\n", automtu="1380", bridge="1400")
    assert "MIG_MTU=1380\n" in written
    assert "from automtu" in said


def test_the_package_is_reached_as_a_module_when_no_script_is_on_path(tmp_path):
    written, said = run(tmp_path, "MIG_PORT=8000\n", module="1360", bridge="1400")
    assert "MIG_MTU=1360\n" in written
    assert "from automtu" in said


def test_the_host_bridge_answers_when_the_probe_cannot(tmp_path):
    written, said = run(tmp_path, "MIG_PORT=8000\n", bridge="1400")
    assert "MIG_MTU=1400\n" in written
    assert "from the docker bridge" in said


def test_nothing_reachable_leaves_the_ethernet_default(tmp_path):
    written, said = run(tmp_path, "MIG_PORT=8000\n")
    assert "MIG_MTU=1500\n" in written
    assert "from the ethernet default" in said


def test_an_existing_setting_is_replaced_rather_than_repeated(tmp_path):
    written, _ = run(tmp_path, "MIG_PORT=8000\nMIG_MTU=1500\n", automtu="1280")
    assert written.count("MIG_MTU=") == 1
    assert "MIG_MTU=1280\n" in written


def test_a_missing_env_file_is_refused_rather_than_invented(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake(bin_dir, "automtu", "echo 1400")
    missing = tmp_path / "absent"
    done = subprocess.run(
        ["sh", str(SCRIPT), str(missing)],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 1
    assert not missing.exists()
    assert "make .env" in done.stderr


def test_a_probe_that_answers_with_prose_is_not_written_as_an_mtu(tmp_path):
    written, said = run(tmp_path, "MIG_PORT=8000\n", automtu="could not detect", bridge="1400")
    assert "MIG_MTU=1400\n" in written
    assert "from the docker bridge" in said
