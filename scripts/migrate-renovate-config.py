#!/usr/bin/env python3
"""Consolidate strict-JSON Renovate configs under .github/renovate.json5."""

import argparse
import json
from pathlib import Path


SHARED_PRESET = "github>michidk/workflows//templates/presets/renovate"
ROOT_NAMES = (
    "renovate.json", "renovate.jsonc", "renovate.json5", ".renovaterc",
    ".renovaterc.json", ".renovaterc.jsonc", ".renovaterc.json5",
)


def merge(older, newer):
    result = dict(older)
    for key, value in newer.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = merge(result[key], value)
        elif isinstance(value, list) and isinstance(result[key], list):
            result[key] = [item for item in result[key] if item not in value] + value
        else:
            result[key] = value
    return result


def migrate(directory, write):
    roots = [directory / name for name in ROOT_NAMES if (directory / name).exists()]
    if not roots:
        print(f"{directory}: no root config")
        return
    if len(roots) != 1:
        raise ValueError(f"{directory}: review multiple root configs manually")
    target = directory / ".github/renovate.json5"
    other_configs = [directory / ".github" / name for name in
                     ("renovate.json", "renovate.jsonc")]
    if any(path.exists() for path in other_configs):
        raise ValueError(f"{directory}: review other .github configs manually")
    older = json.loads(roots[0].read_text())
    newer = json.loads(target.read_text()) if target.exists() else {}
    result = merge(older, newer)
    presets = result.get("extends", [])
    result["extends"] = [SHARED_PRESET] + [
        preset for preset in presets if preset not in (SHARED_PRESET, "config:recommended")
    ]
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if write:
        target.parent.mkdir(exist_ok=True)
        target.write_text(content)
        roots[0].unlink()
    print(f"{directory}: {'migrated' if write else 'would migrate'} {roots[0].name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="apply the migration")
    parser.add_argument("directories", type=Path, nargs="+")
    args = parser.parse_args()
    for directory in args.directories:
        migrate(directory, args.write)


if __name__ == "__main__":
    main()
