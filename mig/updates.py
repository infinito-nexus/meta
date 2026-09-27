"""Which image pin of the roles tree has fallen behind its registry.

Every role names its images in meta/services.yml. The registries answer over
HTTP, which a browser may not ask them directly, so the mirror reads the pins
out of a ref, asks Docker Hub or ghcr for the tags, and keeps the answer.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

HUB = "https://hub.docker.com/v2/repositories"
GHCR = "https://ghcr.io"
PAGE = 100
TTL = 6 * 3600
BLOCK = re.compile(r"^(\w[\w-]*):\s*$")
FIELD = re.compile(r"^  (image|version):\s*[\"']?([^\"'#\n]+?)[\"']?\s*(?:#.*)?$")
# A pin is comparable when it is a number with an optional v and an optional
# suffix: 34-fpm-alpine against 35-fpm-alpine, never against 35-apache.
SHAPE = re.compile(r"^(v?)(\d+(?:\.\d+)*)(\D.*)?$")


class Failed(Exception):
    pass


# Args:
#   text: one role's meta/services.yml as written.
# Returns: [{service, image, version}] for every service that pins both.
def pins(text):
    found = []
    service = ""
    held = {}
    for line in (text or "").splitlines():
        block = BLOCK.match(line)
        if block:
            if held.get("image") and held.get("version"):
                found.append({"service": service, **held})
            service, held = block.group(1), {}
            continue
        field = FIELD.match(line)
        if field and service:
            held[field.group(1)] = field.group(2).strip()
    if held.get("image") and held.get("version"):
        found.append({"service": service, **held})
    return [one for one in found if "{{" not in one["image"] and "{{" not in one["version"]]


# Returns: (prefix, [numbers], suffix) of a pin, or None when it names no
#   version this can compare, such as latest or stable.
def shape(version):
    found = SHAPE.match(version or "")
    if not found:
        return None
    return found.group(1), [int(part) for part in found.group(2).split(".")], (found.group(3) or "")


# Args:
#   version: the pin as the role wrote it.
#   tags: every tag the registry lists.
# Returns: the newest tag of the pin's own shape, or '' when none is newer.
def newest(version, tags):
    held = shape(version)
    if not held:
        return ""
    prefix, numbers, suffix = held
    best, best_numbers = "", numbers
    for tag in tags:
        other = shape(tag)
        if not other or other[0] != prefix or other[2] != suffix:
            continue
        if len(other[1]) != len(numbers):
            continue
        if other[1] > best_numbers:
            best, best_numbers = tag, other[1]
    return best


# Returns: (registry, repository) for an image, or (None, '') for one this
#   cannot ask, such as a private or self-built image.
def registry(image):
    name = (image or "").strip()
    if name.startswith("ghcr.io/"):
        return "ghcr", name[len("ghcr.io/"):]
    if "/" not in name:
        return "hub", f"library/{name}"
    if "." not in name.split("/")[0]:
        return "hub", name
    return None, ""


def _open(url, token="", timeout=30):
    headers = {"Accept": "application/json", "User-Agent": "meta-infinite-graph"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as answer:
        return json.load(answer)


# Args:
#   fetch: (url, token) -> the parsed answer, so a test can hold the network.
# Returns: every tag of an image, newest first where the registry says so.
def tags(image, fetch=_open):
    where, repo = registry(image)
    if not where:
        raise Failed(f"{image} is not on a registry this reads")
    if where == "hub":
        answer = fetch(f"{HUB}/{repo}/tags?page_size={PAGE}&ordering=last_updated", "")
        return [one["name"] for one in (answer.get("results") or [])]
    token = fetch(f"{GHCR}/token?scope=repository:{repo}:pull&service=ghcr.io", "").get("token", "")
    answer = fetch(f"{GHCR}/v2/{repo}/tags/list?n={PAGE}", token)
    return list(answer.get("tags") or [])


def _state(version, latest, failed):
    if failed:
        return "unknown"
    if not shape(version):
        return "floating"
    return "behind" if latest else "current"


# Args:
#   roles: role name -> its meta/services.yml as written.
#   fetch: the network, injected.
# Returns: one entry per pinned image, the ones that fell behind first.
def collect(roles, fetch=_open):
    seen = {}
    found = []
    for role, text in sorted(roles.items()):
        for pin in pins(text):
            image, version = pin["image"], pin["version"]
            if (image, version) not in seen:
                failed, latest = "", ""
                try:
                    latest = newest(version, tags(image, fetch))
                except (Failed, urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as error:
                    failed = str(error)[:200]
                seen[(image, version)] = (latest, failed)
            latest, failed = seen[(image, version)]
            found.append({
                "role": role, "service": pin["service"], "image": image, "version": version,
                "latest": latest, "state": _state(version, latest, failed), "error": failed,
            })
    order = {"behind": 0, "unknown": 1, "floating": 2, "current": 3}
    found.sort(key=lambda one: (order[one["state"]], one["role"], one["service"]))
    return found


# Args:
#   home: where the answer is kept, so a reload costs no second round of
#     registry calls within TTL.
#   fresh: True asks the registries again whatever the cache holds.
def cached(home, roles, fetch=_open, fresh=False, now=time.time):
    path = os.path.join(home, "updates.json")
    if not fresh and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as held:
                answer = json.load(held)
            if now() - answer.get("at", 0) < TTL:
                return answer
        except (OSError, ValueError):
            pass
    answer = {"at": now(), "items": collect(roles, fetch)}
    os.makedirs(home, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out:
        json.dump(answer, out)
    return answer
