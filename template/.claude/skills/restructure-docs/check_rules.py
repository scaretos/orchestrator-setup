#!/usr/bin/env python3
"""Check .claude/rules/ frontmatter and simulate path matching.

Every rule has a paths: list. A glob that matches no repository file is dead:
it can never load the rule by this model, and the fact in it is effectively
lost. This script expands every glob against git ls-files and reports dead
ones. With file arguments it also reports which rules a given file would load,
the folder CLAUDE.md files above it, and their total size, so you can see
whether a rule is too broad. With --shared it lists files that load more than
one rule.

This simulates matching only; it does not prove what the Claude Code runtime
actually loads. Verify the model against the installed version and its docs.

Usage:
  python check_rules.py --repo .
  python check_rules.py --repo . --shared
  python check_rules.py --repo . src/App/Pages/InvoicePage.cs src/Lib/TaxCalculator.cs

Exits 1 when a rule has no paths or a glob hits nothing.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
LIST_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")
QUOTED = re.compile(r"""["']([^"']+)["']""")


def git_files(repo: Path, excludes):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-co", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(f"git ls-files failed in {repo}: {exc}")
    files = []
    for f in out.splitlines():
        if not f:
            continue
        posix = f.replace("\\", "/")
        if any(posix.startswith(prefix) for prefix in excludes):
            continue
        files.append(posix)
    return files


def glob_to_regex(glob: str):
    out = []
    i = 0
    while i < len(glob):
        char = glob[i]
        if char == "*" and i + 1 < len(glob) and glob[i + 1] == "*":
            if i + 2 < len(glob) and glob[i + 2] == "/":
                out.append("(?:.*/)?")
                i += 3
            else:
                out.append(".*")
                i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def parse_paths(text: str):
    match = FRONTMATTER.match(text)
    if not match:
        return None
    lines = match.group(1).splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("paths:"):
            continue
        rest = line[len("paths:"):].strip()
        if rest:
            return [p.replace("\\", "/") for p in QUOTED.findall(rest)]
        values = []
        for following in lines[index + 1:]:
            if not following.startswith((" ", "\t")):
                break
            item = LIST_ITEM.match(following)
            if item:
                value = item.group(1)
                quoted = QUOTED.findall(value)
                values.append((quoted[0] if quoted else value).replace("\\", "/"))
        return values
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--rules-dir", default=".claude/rules", help="rules folder (default: .claude/rules)")
    parser.add_argument("--exclude", default=".git/,.claude/worktrees/",
                        help="comma-separated path prefixes to ignore")
    parser.add_argument("--shared", action="store_true",
                        help="list files that load more than one rule")
    parser.add_argument("files", nargs="*", help="files to probe: which rules would they load?")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    excludes = tuple(x.strip().replace("\\", "/") for x in args.exclude.split(",") if x.strip())
    files = git_files(repo, excludes)

    rules_dir = repo / args.rules_dir
    if not rules_dir.is_dir():
        sys.exit(f"no rules folder: {rules_dir}")

    rules = []
    errors = []
    for path in sorted(rules_dir.rglob("*.md")):
        rel = str(path.relative_to(repo)).replace("\\", "/")
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        paths = parse_paths(text)
        if paths is None:
            errors.append(f"{rel}: no frontmatter or no paths: list")
            continue
        if not paths:
            errors.append(f"{rel}: paths: is empty")
            continue
        rules.append({
            "file": rel,
            "paths": paths,
            "size": len(text.encode("utf-8")),
            "matchers": [glob_to_regex(p) for p in paths],
        })

    if args.files:
        for probe in args.files:
            rel = probe.replace("\\", "/")
            if os.path.isabs(rel):
                rel = str(Path(rel).resolve().relative_to(repo)).replace("\\", "/")
            hits = [r for r in rules if any(m.match(rel) for m in r["matchers"])]
            total = sum(r["size"] for r in hits)
            print(f"{rel} -> " + (", ".join(f"{r['file']} ({r['size']})" for r in hits) or "no rule")
                  + f"  total {total}")
            target = (repo / rel).resolve()
            try:
                target.relative_to(repo)
                parent = target.parent
            except ValueError:
                parent = repo
            claude_files = []
            while True:
                candidate = parent / "CLAUDE.md"
                if candidate.is_file():
                    claude_files.append((
                        str(candidate.relative_to(repo)).replace("\\", "/"),
                        len(candidate.read_bytes()),
                    ))
                if parent == repo:
                    break
                parent = parent.parent
            if claude_files:
                print("    CLAUDE.md: " + ", ".join(f"{name} ({size})" for name, size in claude_files)
                      + f"  total {sum(size for _, size in claude_files)}")
        return

    if args.shared:
        by_file = {}
        for rule in rules:
            for f in files:
                if any(m.match(f) for m in rule["matchers"]):
                    by_file.setdefault(f, []).append(rule["file"])
        shared = {f: rs for f, rs in by_file.items() if len(rs) > 1}
        for f in sorted(shared):
            print(f"{f:<60} {len(shared[f])} rules: {', '.join(shared[f])}")
        print(f"\n{len(shared)} file(s) load more than one rule")
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        if errors:
            sys.exit(1)
        return

    dead = 0
    for rule in rules:
        counts = [sum(1 for f in files if matcher.match(f)) for matcher in rule["matchers"]]
        unique = len({f for matcher in rule["matchers"] for f in files if matcher.match(f)})
        zero = [glob for glob, count in zip(rule["paths"], counts) if not count]
        if zero:
            dead += len(zero)
        line = f"{rule['file']:<48} {unique:5d} files"
        if zero:
            line += "   NO HIT: " + ", ".join(zero)
        print(line)

    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    if dead:
        print(f"\n{dead} dead glob(s): these rules can never load through that path.", file=sys.stderr)
    elif errors:
        print(f"\n{len(errors)} rule(s) with a frontmatter problem.", file=sys.stderr)
    else:
        print("\nevery glob hits at least one file")
    if dead or errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
