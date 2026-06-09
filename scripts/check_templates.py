#!/usr/bin/env python3
"""
Walk every .html file under app/templates/ and confirm Jinja can parse it.
Catches broken syntax (missing endif, typoed block, etc.) before deploy.

Returns non-zero exit if any template fails to parse, prints all errors.
"""

from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = REPO_ROOT / "app" / "templates"


def main() -> int:
    if not TEMPLATE_ROOT.exists():
        print(f"Template directory not found: {TEMPLATE_ROOT}", file=sys.stderr)
        return 1

    env = Environment(loader=FileSystemLoader(TEMPLATE_ROOT))

    errors: list[tuple[Path, str]] = []
    checked = 0
    for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
        checked += 1
        try:
            env.parse(path.read_text(encoding="utf-8"))
        except TemplateSyntaxError as exc:
            errors.append((path, f"line {exc.lineno}: {exc.message}"))
        except Exception as exc:
            errors.append((path, f"{type(exc).__name__}: {exc}"))

    if errors:
        print(f"❌ {len(errors)} template(s) failed to parse:", file=sys.stderr)
        for path, msg in errors:
            rel = path.relative_to(REPO_ROOT)
            print(f"  {rel}: {msg}", file=sys.stderr)
        return 1

    print(f"✓ {checked} templates parse cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
