#!/usr/bin/env python3
"""
Validate a SKILL.md file: parse the YAML frontmatter and check the fields that
both Hermes and OpenClaw (the agentskills.io standard) require.

Usage: python tests/validate_skill.py path/to/SKILL.md
"""

import re
import sys

import yaml

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
MAX_DESCRIPTION = 160  # OpenClaw's documented limit; keep skills portable.


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with a '---' YAML frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not closed with a second '---'")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return data


def validate(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        fm = parse_frontmatter(f.read())

    errors = []
    name = fm.get("name")
    desc = fm.get("description")

    if not name:
        errors.append("missing required field: name")
    elif not NAME_RE.match(str(name)):
        errors.append(f"name '{name}' must match ^[a-z][a-z0-9_-]*$")

    if not desc:
        errors.append("missing required field: description")
    else:
        desc = str(desc)
        if "\n" in desc:
            errors.append("description must be a single line")
        if len(desc) > MAX_DESCRIPTION:
            errors.append(f"description is {len(desc)} chars (max {MAX_DESCRIPTION})")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_skill.py path/to/SKILL.md", file=sys.stderr)
        return 2
    path = sys.argv[1]
    try:
        errors = validate(path)
    except (ValueError, OSError) as e:
        print(f"INVALID {path}: {e}", file=sys.stderr)
        return 1
    if errors:
        print(f"INVALID {path}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
