#!/usr/bin/env bash
# Param: release <ref>                    the newest vX.Y.Z tag reachable from <ref>, without the v
# Param: tags <repo> <version> <stamp>    every ref one build publishes, one per line
# Param: push-needed <candidate> <repo> <version>
#                                         true, or false when <repo>:<version> is out and the local
#                                         <candidate> carries what <repo>:latest carries
# Param: manifest <repo> <version>        fails unless <repo>:latest and every prefix of <version>
#                                         point at one image
set -euo pipefail

RELEASE_TAG='^v[0-9]+\.[0-9]+\.[0-9]+$'
RELEASE_VERSION='^[0-9]+\.[0-9]+\.[0-9]+$'

CONTENT='apk info -v | sort; find /docker-entrypoint.sh /docker-entrypoint.d /etc/nginx /usr/local/lib/mig /usr/share/nginx/html -type f -exec sha256sum {} \; | sort'

fail() {
  echo "publish: $1" >&2
  exit 1
}

need_version() {
  [[ "$1" =~ ${RELEASE_VERSION} ]] || fail "'$1' is not an X.Y.Z release"
}

release() {
  local listed newest
  listed="$(git tag --merged "$1" --sort=-v:refname)"
  newest="$(grep -m1 -E "${RELEASE_TAG}" <<<"${listed}")" || fail "no vX.Y.Z tag is reachable from $1"
  echo "${newest#v}"
}

prefixes() {
  local -a parts
  IFS=. read -ra parts <<<"$1"
  local acc="${parts[0]}" i
  echo "${acc}"
  for ((i = 1; i < ${#parts[@]}; i++)); do
    acc+=".${parts[i]}"
    echo "${acc}"
  done
}

tags() {
  local repo="$1" version="$2" stamp="$3" prefix
  need_version "${version}"
  [[ "${stamp}" =~ ^[0-9]+$ ]] || fail "'${stamp}' is not a unix timestamp"
  echo "${repo}:latest"
  while read -r prefix; do
    echo "${repo}:${prefix}"
  done < <(prefixes "${version}")
  echo "${repo}:${version}.${stamp}"
}

fingerprint() {
  docker run --rm --pull "$2" --entrypoint sh "$1" -c "${CONTENT}" | sha256sum
}

push_needed() {
  local candidate="$1" repo="$2" version="$3" built published
  need_version "${version}"
  built="$(fingerprint "${candidate}" never)"
  published="$(fingerprint "${repo}:latest" always || true)"
  if [[ "${built}" != "${published}" ]]; then
    echo "publish: ${candidate} differs from ${repo}:latest, pushing" >&2
    echo true
  elif ! docker buildx imagetools inspect "${repo}:${version}" >/dev/null 2>&1; then
    echo "publish: ${repo}:${version} is not out yet, pushing" >&2
    echo true
  else
    echo "publish: unchanged since the published ${version}, nothing to push" >&2
    echo false
  fi
}

digest_of() {
  docker buildx imagetools inspect "$1" --format '{{json .Manifest.Digest}}'
}

manifest() {
  local repo="$1" version="$2" latest prefix
  need_version "${version}"
  latest="$(digest_of "${repo}:latest")"
  while read -r prefix; do
    [[ "$(digest_of "${repo}:${prefix}")" == "${latest}" ]] ||
      fail "${repo}:latest and :${prefix} point at different images; whoever pinned ${prefix} stopped receiving what latest gets"
  done < <(prefixes "${version}")
  echo "publish: ${repo}:latest == every prefix of ${version}"
}

action="${1:?usage: publish.sh release|tags|push-needed|manifest ...}"
shift
case "${action}" in
release) release "${1:?ref}" ;;
tags) tags "${1:?repo}" "${2:?version}" "${3:?stamp}" ;;
push-needed) push_needed "${1:?candidate}" "${2:?repo}" "${3:?version}" ;;
manifest) manifest "${1:?repo}" "${2:?version}" ;;
*) fail "unknown action '${action}'" ;;
esac
