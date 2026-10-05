# Changelog

## [2.0.2] - 2026-10-05

Repairs the 2.0.1 release, which published no image either.

- *make lint* ran before anything had filled the gitignored *src/vendor*
- A fresh checkout held no vendored module, so the test job died in the lint
- *lint* now depends on *vendor*, as the other test targets already did

## [2.0.1] - 2026-10-05

Repairs the 2.0.0 release, which published no image.

### Fixed

- preact 11 renamed its ESM builds to *.mjs*; vendoring threw and e2e died
- Every one of the eighteen vendored paths is checked, not just the first
- *make test* installs the pytest it needs; the test job died on its absence

## [2.0.0] - 2026-10-05

Publishes as *meta*, serves the page without an inline script, and lets the
whole test suite gate a release for the first time.

### Breaking

- The image is now *ghcr.io/infinito-nexus/meta*, not *infinito-mig*
- Its name follows the repository, so a fork publishes under its own
- Consumers pinning the old name must repoint; infinito-nexus/core did
- A push to main without a tag no longer publishes, only tags do

### Fixed

- The page carries no inline script, so a strict CSP no longer blocks it
- An import map has no external form, so the modules import by path instead
- Vendoring rewrites preact's own bare *preact* import, which needs no map
- It throws when upstream stops shipping that import, rather than going quiet
- Vendored modules are marked *@ts-nocheck*; tsconfig's exclude does not
  reach a module imported by path, and *make lint* was checking three
  thousand lines of third-party build output
- A release triggered twice, once for main and once for the tag of one commit

### Tests

- *make test* runs every suite: lints, types, server units, Playwright
- The browser-only suite is *make test-browser*
- CI gates the build on that suite beside the HTTP smoke test; before, 146
  Playwright specs, 9 lints and 26 server units never gated a release
- A lint keeps the page free of inline scripts and the vendor tree free of
  bare specifiers

## [1.0.3] - 2026-10-04

Lets replicas share one git volume; a losing clone no longer kills the mirror.

### Fixed

- Mirror cloned into a staging directory and renamed in, so the first writer wins
- A loser's rename fails on the non-empty target and drops only its own copy
- Previously a loser's *rm -rf* took the winner's mirror, wedging */git/* on 502
- Replicas can share one volume without a node pin or a single replica

## [1.0.2] - 2026-10-02

Repairs the image pipeline, stuck at e2e since 1.0.0; completes translations.

### Fixed

- e2e checks out infinito-nexus/core next to meta, the roles mount was empty
- No image was published for 1.0.0 or 1.0.1, both tags stopped at e2e
- Dropped BASE_IMAGE and PORT from the e2e call, nothing read them

### Translations

- The updates view speaks all 184 languages, with each one's plural forms
- The shortened search is retranslated, no view says "search the runs" now

### Tests

- The facet test measures the bond axis instead of pinning 123 rows
- The second-card test checks each frame that both cards coexist
- The overview test closes a held popup, so a dead close button fails it

### Dependencies

- js-yaml 5.4.1 to 5.4.2, simple-icons 16.29.0 to 16.33.0
- typescript 6.0.3 to 7.0.2 (dev)
- build-push-action 6.19.2 to 7.4.0
- upload-artifact 4 to 7, download-artifact 4 to 8

## [1.0.1] - 2026-10-01

Closes all 17 code scanning alerts and repairs the build.

### Security

- Pinned all six docker action refs to commit hashes, majors unified
- Artifacts opened to the serving group at 0750/0640, not world readable
- Test server refuses any path resolving outside the tree it serves
- Embed assertion anchored to the start of the URL
- Translate script validates the language code, reads without an existsSync race

### Fixed

- *make vendor* aborted since the bumps, taking *make test* and *make up* along
- three has no UMD build past r159, js-yaml 5 moved its browser builds
- three is vendored as a module now, reached through the page's import map

### Changed

- Both workflows group by ref, so a push cancels the run it supersedes
- The image pipeline never cancels a tag, so a release always finishes

### Dependencies

- 3d-force-graph 1.73.4 to 1.80.0, three 0.146 to 0.186.0
- js-yaml 4.1.0 to 5.4.1, node 22-alpine to 25-alpine
- @playwright/test 1.61.1 to 1.63.0
- checkout 4 to 7, metadata 5 to 6, login 3 to 4, setup-buildx 3 to 4

### Upgrading

- Image and compose set MIG_ARTIFACT_GROUP=nginx, nothing to do
- An own environment leaving it empty makes nginx answer 403 for artifacts

## [1.0.0] - 2026-10-01

Official Release🥳
