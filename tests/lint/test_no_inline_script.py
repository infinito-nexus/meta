import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPENING = re.compile(r"<script(?P<attrs>[^>]*)>", re.I)
HAS_SRC = re.compile(r"\bsrc\s*=", re.I)
BARE_IMPORT = re.compile(r"""\bfrom\s*['"]([^'".][^'"]*)['"]""")
MODULES = {"three.module.js", "three.core.js", "preact.module.js", "hooks.module.js", "htm.module.js"}


def pages():
    for path in sorted(SRC.rglob("*.html")):
        if {"vendor", "roles", "infinito_meta"} & set(path.parts):
            continue
        yield path.relative_to(ROOT), path.read_text(encoding="utf-8")


def test_no_page_carries_an_inline_script():
    offenders = [
        f"{path}: <script{match.group('attrs').strip()}>"
        for path, body in pages()
        for match in OPENING.finditer(body)
        if not HAS_SRC.search(match.group("attrs"))
    ]
    assert not offenders, (
        "a Content-Security-Policy without 'unsafe-inline' blocks these, and the "
        "deployment that serves this page sets one:\n  " + "\n  ".join(offenders)
    )


def test_no_vendored_module_imports_a_bare_specifier():
    vendored = [path for path in (SRC / "vendor").rglob("*.js") if path.name in MODULES]
    assert vendored, "src/vendor holds no module; run `make vendor` first"
    offenders = [
        f"{path.relative_to(ROOT)}: {specifier}"
        for path in vendored
        for specifier in BARE_IMPORT.findall(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "a bare specifier resolves only through an import map, which exists only "
        "inline; scripts/vendor.js rewrites these:\n  " + "\n  ".join(offenders)
    )
