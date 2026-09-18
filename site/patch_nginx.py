#!/usr/bin/env python3
"""Insert the referral proxy into every dbskill.site server block."""
from pathlib import Path
import re
import sys


def patch(text: str, snippet: str) -> str:
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    depth = 0
    server_start = None
    found = 0
    for line in lines:
        if depth == 0 and re.match(r"^\s*server\s*\{\s*$", line):
            server_start = len(result)
        result.append(line)
        uncommented = line.split("#", 1)[0]
        depth += uncommented.count("{") - uncommented.count("}")
        if server_start is None or depth != 0:
            continue
        start = server_start
        block = result[start:]
        server_start = None
        if not re.search(r"\bserver_name\s+[^;]*\bdbskill\.site\b", "".join(block)):
            continue
        found += 1
        existing = "".join(block)
        if "location ^~ /referral/" in existing:
            if "location = /referral" not in existing:
                raise ValueError("incomplete referral location in dbskill.site server block")
            continue
        insertion = next(
            (i for i, item in enumerate(block) if re.match(r"^\s*location\s+/\s*\{", item)),
            len(block) - 1,
        )
        block.insert(insertion, snippet.rstrip() + "\n\n")
        result[start:] = block
    if depth != 0:
        raise ValueError("unbalanced nginx configuration")
    if found == 0:
        raise ValueError("no dbskill.site server block found")
    return "".join(result)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    snippet_path = Path(sys.argv[2])
    updated = patch(path.read_text(encoding="utf-8"), snippet_path.read_text(encoding="utf-8"))
    path.write_text(updated, encoding="utf-8")
