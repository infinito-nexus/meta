import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mig"))

import updates  # noqa: E402

CORE = Path("/home/kevinveenbirkenbach/Repositories/github.com/kevinveenbirkenbach/infinito-nexus-core")

SERVICES = """---
nextcloud:
  name: nextcloud
  image: nextcloud
  version: 34-fpm-alpine
proxy:
  image: nginx
  version: 1.31.5-alpine
agent:
  image: ghcr.io/nextcloud/context_agent
  version: 2.8.0
built:
  image: "{{ NEXTCLOUD_IMAGE }}"
  version: "{{ NEXTCLOUD_VERSION }}"
floating:
  image: redis
  version: latest
"""

TAGS = {
    "nextcloud": ["34-fpm-alpine", "35-fpm-alpine", "35-apache", "36-fpm", "latest"],
    "nginx": ["1.31.5-alpine", "1.31.6-alpine", "1.32.0", "stable-alpine"],
    "ghcr.io/nextcloud/context_agent": ["2.8.0", "2.9.1", "3.0.0-beta"],
    "redis": ["7.4.1", "latest"],
}


def fake(url, token=""):
    if "/token?" in url:
        return {"token": "t"}
    if url.startswith(updates.HUB):
        repo = url[len(updates.HUB) + 1:].split("/tags")[0]
        name = repo[len("library/"):] if repo.startswith("library/") else repo
        return {"results": [{"name": tag} for tag in TAGS[name]]}
    repo = url[len(updates.GHCR) + len("/v2/"):].split("/tags/list")[0]
    return {"tags": TAGS[f"ghcr.io/{repo}"]}


def test_a_role_file_gives_up_every_pin_it_states():
    found = {one["service"]: one for one in updates.pins(SERVICES)}
    assert set(found) == {"nextcloud", "proxy", "agent", "floating"}, "a templated pin names no version to compare"
    assert (found["nextcloud"]["image"], found["nextcloud"]["version"]) == ("nextcloud", "34-fpm-alpine")
    assert found["agent"]["image"] == "ghcr.io/nextcloud/context_agent"


def test_a_newer_tag_counts_only_when_it_has_the_pin_s_own_shape():
    assert updates.newest("34-fpm-alpine", TAGS["nextcloud"]) == "35-fpm-alpine", "36-fpm is another flavour"
    assert updates.newest("1.31.5-alpine", TAGS["nginx"]) == "1.31.6-alpine", "1.32.0 drops the suffix"
    assert updates.newest("2.8.0", TAGS["ghcr.io/nextcloud/context_agent"]) == "2.9.1"
    assert updates.newest("2.9.1", TAGS["ghcr.io/nextcloud/context_agent"]) == "", "nothing above it"
    assert updates.newest("latest", TAGS["redis"]) == "", "a floating pin compares to nothing"


def test_every_kind_of_pin_reaches_the_table_with_its_state():
    found = {one["service"]: one for one in updates.collect({"web-app-x": SERVICES}, fake)}
    assert found["nextcloud"]["state"] == "behind" and found["nextcloud"]["latest"] == "35-fpm-alpine"
    assert found["agent"]["state"] == "behind"
    assert found["floating"]["state"] == "floating", "latest is a pin nothing can measure"
    assert [one["state"] for one in updates.collect({"web-app-x": SERVICES}, fake)][0] == "behind", \
        "what fell behind is read first"

    def refuses(url, token=""):
        raise OSError("no route to the registry")

    blind = {one["service"]: one for one in updates.collect({"web-app-x": SERVICES}, refuses)}
    assert blind["nextcloud"]["state"] == "unknown"
    assert "no route" in blind["nextcloud"]["error"]


def test_an_image_names_the_registry_that_answers_for_it():
    assert updates.registry("nginx") == ("hub", "library/nginx")
    assert updates.registry("nextcloud/aio") == ("hub", "nextcloud/aio")
    assert updates.registry("ghcr.io/nextcloud/context_agent") == ("ghcr", "nextcloud/context_agent")
    assert updates.registry("registry.example.com/team/app")[0] is None, "a private registry is not asked"


def test_the_answer_is_kept_until_it_goes_stale(tmp_path):
    calls = []

    def counting(url, token=""):
        calls.append(url)
        return fake(url, token)

    clock = [1000.0]
    first = updates.cached(str(tmp_path), {"r": SERVICES}, counting, now=lambda: clock[0])
    again = updates.cached(str(tmp_path), {"r": SERVICES}, counting, now=lambda: clock[0])
    assert again["items"] == first["items"]
    spent = len(calls)

    clock[0] += updates.TTL + 1
    updates.cached(str(tmp_path), {"r": SERVICES}, counting, now=lambda: clock[0])
    assert len(calls) > spent, "once it is stale the registries are asked again"
    updates.cached(str(tmp_path), {"r": SERVICES}, counting, fresh=True, now=lambda: clock[0])
    assert len(calls) > spent


def test_the_real_roles_tree_parses_into_pins():
    if not CORE.exists():
        pytest.skip("the core checkout is not here")
    roles = {}
    for path in sorted(CORE.glob("roles/*/meta/services.yml")):
        roles[path.parents[1].name] = path.read_text(encoding="utf-8")
    found = [pin for text in roles.values() for pin in updates.pins(text)]
    assert len(found) > 100, f"only {len(found)} pins parsed out of {len(roles)} role files"
    assert all(pin["image"] and pin["version"] for pin in found)
    assert any(pin["image"].startswith("ghcr.io/") for pin in found)
    comparable = [pin for pin in found if updates.shape(pin["version"])]
    assert len(comparable) > len(found) / 2, "most pins state a version this can compare"


def test_a_real_registry_answers_the_shape_of_a_pin():
    try:
        listed = updates.tags("nginx")
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"the registry is not reachable here: {error}")
    assert listed, "the registry listed no tag at all"
    assert any(updates.shape(tag) for tag in listed)
    assert json.dumps(listed[:3]), "tag names come back as plain strings"
