#!/usr/bin/env python3
"""Select gh-settings targets from Orcastrate's repository inventory."""

import argparse
import json
from pathlib import Path
import tomllib


def select_repositories(config: Path, repository: str = "") -> list[str]:
    with config.open("rb") as source:
        names = [repo["name"] for repo in tomllib.load(source)["repos"]]
    if not names or len(names) != len(set(names)):
        raise ValueError("Orcastrate inventory must be nonempty and contain no duplicates")
    if repository:
        if repository not in names:
            raise ValueError(f"Repository is not managed by Orcastrate: {repository}")
        return [repository]
    return names


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("orchestrator.toml"))
    parser.add_argument("--repository", default="")
    args = parser.parse_args()
    try:
        repositories = select_repositories(args.config, args.repository)
        print(json.dumps({"include": [
            {"repository": name, "owner": name.split("/")[0], "name": name.split("/")[1]}
            for name in repositories
        ]}))
    except (KeyError, ValueError) as error:
        parser.error(str(error))
