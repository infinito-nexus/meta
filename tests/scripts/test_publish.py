import os
import pathlib
import subprocess

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "publish.sh"
REPO = "ghcr.io/o/meta"
CANDIDATE = "meta:candidate"
SAME = "nginx-1.29.3-r1\npython3-3.12.12-r0\n9f86d0 /usr/share/nginx/html/index.html\n"
DIGEST = '"sha256:aaaa"\n'

FAKE_DOCKER = r'''#!/bin/sh
printf '%s\n' "$*" >> "$FAKE/calls"
case "$1" in
  run) file="$FAKE/run/$(printf %s "$7" | tr /: __)" ;;
  buildx) file="$FAKE/digest/$(printf %s "$4" | tr /: __)" ;;
  *) exit 2 ;;
esac
[ -f "$file" ] || exit 1
cat "$file"
'''

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def key(ref):
    return ref.replace("/", "_").replace(":", "_")


def registry(tmp_path, contents, digests):
    """Args:
        contents: image -> what its content probe prints; an absent image fails to run.
        digests: ref -> what imagetools reports for it; an absent ref is not published.

    Returns: the environment publish.sh runs in, with docker replaced by the fake.
    """
    fake = tmp_path / "fake"
    for sub, table in (("run", contents), ("digest", digests)):
        (fake / sub).mkdir(parents=True)
        for ref, text in table.items():
            (fake / sub / key(ref)).write_text(text, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER, encoding="utf-8")
    docker.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE": str(fake)}


def publish(env, *args, cwd=None):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env, cwd=cwd, capture_output=True, text=True, check=False,
    )


def calls(env):
    return pathlib.Path(env["FAKE"], "calls").read_text(encoding="utf-8").splitlines()


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, check=True)


def commit_tagged(cwd, tag):
    git(cwd, "commit", "-q", "--allow-empty", "-m", tag)
    git(cwd, "tag", tag)


def test_the_release_is_the_newest_version_tag_reachable_from_the_ref(tmp_path):
    git(tmp_path, "init", "-q")
    for tag in ("v1.9.0", "v1.10.0", "v2.0.0-rc1", "latest"):
        commit_tagged(tmp_path, tag)
    commit_tagged(tmp_path, "v3.0.0")

    done = publish(GIT_ENV, "release", "latest", cwd=tmp_path)

    assert done.returncode == 0, done.stderr
    assert done.stdout == "1.10.0\n"


def test_a_ref_without_a_release_tag_is_refused(tmp_path):
    git(tmp_path, "init", "-q")
    commit_tagged(tmp_path, "latest")

    done = publish(GIT_ENV, "release", "HEAD", cwd=tmp_path)

    assert done.returncode == 1
    assert not done.stdout
    assert "no vX.Y.Z tag" in done.stderr


def test_one_build_publishes_latest_every_prefix_and_a_stamped_release():
    done = publish(os.environ, "tags", REPO, "2.0.4", "1767225600")

    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [
        f"{REPO}:latest",
        f"{REPO}:2",
        f"{REPO}:2.0",
        f"{REPO}:2.0.4",
        f"{REPO}:2.0.4.1767225600",
    ]


@pytest.mark.parametrize("version, stamp", [
    ("2.0", "1767225600"),
    ("v2.0.4", "1767225600"),
    ("", "1767225600"),
    ("2.0.4", "now"),
])
def test_tags_are_refused_for_what_is_not_a_release(version, stamp):
    done = publish(os.environ, "tags", REPO, version, stamp)

    assert done.returncode == 1
    assert not done.stdout


def test_an_unchanged_rebuild_of_a_published_release_pushes_nothing(tmp_path):
    env = registry(tmp_path, {CANDIDATE: SAME, f"{REPO}:latest": SAME}, {f"{REPO}:2.0.4": DIGEST})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    assert done.returncode == 0, done.stderr
    assert done.stdout == "false\n"


def test_a_changed_package_pushes(tmp_path):
    newer = SAME.replace("nginx-1.29.3-r1", "nginx-1.29.3-r2")
    env = registry(tmp_path, {CANDIDATE: newer, f"{REPO}:latest": SAME}, {f"{REPO}:2.0.4": DIGEST})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    assert done.returncode == 0, done.stderr
    assert done.stdout == "true\n"


def test_a_changed_served_file_pushes(tmp_path):
    newer = SAME.replace("9f86d0", "60303a")
    env = registry(tmp_path, {CANDIDATE: newer, f"{REPO}:latest": SAME}, {f"{REPO}:2.0.4": DIGEST})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    assert done.stdout == "true\n"


def test_a_release_not_yet_out_pushes_even_when_the_content_matches(tmp_path):
    env = registry(tmp_path, {CANDIDATE: SAME, f"{REPO}:latest": SAME}, {})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.5")

    assert done.returncode == 0, done.stderr
    assert done.stdout == "true\n"


def test_a_registry_without_latest_pushes(tmp_path):
    env = registry(tmp_path, {CANDIDATE: SAME}, {f"{REPO}:2.0.4": DIGEST})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    assert done.returncode == 0, done.stderr
    assert done.stdout == "true\n"


def test_a_candidate_that_cannot_be_probed_fails_rather_than_pushes(tmp_path):
    env = registry(tmp_path, {f"{REPO}:latest": SAME}, {f"{REPO}:2.0.4": DIGEST})

    done = publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    assert done.returncode == 1
    assert not done.stdout
    assert any(f"--pull never --entrypoint sh {CANDIDATE} -c " in call for call in calls(env))


def test_the_published_latest_is_pulled_and_the_candidate_is_not(tmp_path):
    env = registry(tmp_path, {CANDIDATE: SAME, f"{REPO}:latest": SAME}, {f"{REPO}:2.0.4": DIGEST})

    publish(env, "push-needed", CANDIDATE, REPO, "2.0.4")

    runs = [call for call in calls(env) if call.startswith("run ")]
    assert len(runs) == 2
    assert any(f"--pull always --entrypoint sh {REPO}:latest -c " in run for run in runs)
    assert any(f"--pull never --entrypoint sh {CANDIDATE} -c " in run for run in runs)
    for run in runs:
        assert "apk info -v" in run
        assert "/usr/share/nginx/html" in run


def prefix_digests():
    return {f"{REPO}:{tag}": DIGEST for tag in ("latest", "2", "2.0", "2.0.4")}


def test_latest_and_every_release_prefix_on_one_image_pass(tmp_path):
    env = registry(tmp_path, {}, prefix_digests())

    done = publish(env, "manifest", REPO, "2.0.4")

    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("drifted", ["2", "2.0", "2.0.4"])
def test_a_release_prefix_drifting_from_latest_fails(tmp_path, drifted):
    digests = prefix_digests()
    digests[f"{REPO}:{drifted}"] = '"sha256:bbbb"\n'
    env = registry(tmp_path, {}, digests)

    done = publish(env, "manifest", REPO, "2.0.4")

    assert done.returncode == 1
    assert f":{drifted} point at different images" in done.stderr


def test_a_missing_release_prefix_fails(tmp_path):
    digests = prefix_digests()
    del digests[f"{REPO}:2.0"]
    env = registry(tmp_path, {}, digests)

    done = publish(env, "manifest", REPO, "2.0.4")

    assert done.returncode == 1
    assert ":2.0 point at different images" in done.stderr
