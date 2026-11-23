#!/usr/bin/env python3
"""Check .claude/rules/ frontmatter and simulate path matching.

A rule with a paths: list loads when a matching file is read or edited. A rule
without paths: loads at launch in every session, like the root CLAUDE.md; it
is reported with its size, not as an error, because that cost is paid by
every session. A glob that matches no repository file is dead: by this model
the rule can never load through it.

The script expands every glob (including brace groups such as
src/**/*.{ts,tsx}) against git ls-files and reports dead ones. With file
arguments it prints which rules each file would load, the rules loaded at
launch, the folder CLAUDE.md files above it and the total, and flags a total
over --budget. With --shared it lists files that load more than one rule.

This simulates matching only; it does not prove what the Claude Code runtime
loaded. Confirm loading with a real read (see the skill, step 5).

Usage:
  python check_rules.py --repo .
  python check_rules.py --repo . --shared
  python check_rules.py --repo . --budget 20000 src/api/orders.ts lib/util/dates.ts

Exits 1 when a glob hits nothing, a paths: list is empty, or a probe is over
the budget.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
LIST_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")


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


def split_top_level(text: str):
    """Split on commas that are not inside a {brace group}."""
    parts, depth, current = [], 0, []
    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def expand_braces(glob: str):
    """src/*.{ts,tsx} -> [src/*.ts, src/*.tsx]; groups nest and multiply."""
    start = glob.find("{")
    if start < 0:
        return [glob]
    depth = 0
    for end in range(start, len(glob)):
        if glob[end] == "{":
            depth += 1
        elif glob[end] == "}":
            depth -= 1
            if depth == 0:
                break
    else:
        return [glob]  # unbalanced: treat literally
    head, body, tail = glob[:start], glob[start + 1:end], glob[end + 1:]
    options = split_top_level(body)
    if len(options) < 2:
        return [head + "{" + body + "}" + t for t in expand_braces(tail)]
    result = []
    for option in options:
        result.extend(expand_braces(head + option + tail))
    return result


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


def unquote(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_paths(text: str):
    """The paths: globs, [] for an empty list, or None when there is no paths: field.

    Accepts a YAML list, an inline [a, b] list, or a comma-separated string,
    quoted or not.
    """
    match = FRONTMATTER.match(text)
    if not match:
        return None
    lines = match.group(1).splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("paths:"):
            continue
        rest = line[len("paths:"):].strip()
        if rest:
            if rest.startswith("[") and rest.endswith("]"):
                rest = rest[1:-1]
            rest = unquote(rest) if rest.count('"') == 2 or rest.count("'") == 2 else rest
            values = [unquote(v) for v in split_top_level(rest)]
            return [v.replace("\\", "/") for v in values if v]
        values = []
        for following in lines[index + 1:]:
            if not following.startswith((" ", "\t")):
                break
            item = LIST_ITEM.match(following)
            if item:
                value = unquote(item.group(1))
                if value:
                    values.append(value.replace("\\", "/"))
        return values
    return None


def compile_globs(paths):
    """One entry per written glob, each with the regexes of its brace expansions."""
    return [(glob, [glob_to_regex(g) for g in expand_braces(glob)]) for glob in paths]


def matches(rule, rel):
    return any(m.match(rel) for _, regexes in rule["globs"] for m in regexes)


def claude_md_above(repo: Path, rel: str):
    target = (repo / rel).resolve()
    try:
        target.relative_to(repo)
        parent = target.parent
    except ValueError:
        parent = repo
    found = []
    while True:
        candidate = parent / "CLAUDE.md"
        if candidate.is_file():
            found.append((str(candidate.relative_to(repo)).replace("\\", "/"), len(candidate.read_bytes())))
        if parent == repo or parent == parent.parent:
            break
        parent = parent.parent
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--rules-dir", default=".claude/rules", help="rules folder (default: .claude/rules)")
    parser.add_argument("--exclude", default=".git/,.claude/worktrees/",
                        help="comma-separated path prefixes to ignore")
    parser.add_argument("--shared", action="store_true",
                        help="list files that load more than one rule")
    parser.add_argument("--budget", type=int, default=0,
                        help="with probes: flag a file whose loaded total exceeds this many bytes")
    parser.add_argument("files", nargs="*", help="files to probe: which rules would they load?")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    excludes = tuple(x.strip().replace("\\", "/") for x in args.exclude.split(",") if x.strip())
    files = git_files(repo, excludes)

    rules_dir = repo / args.rules_dir
    if not rules_dir.is_dir():
        sys.exit(f"no rules folder: {rules_dir}")

    scoped, always, errors = [], [], []
    for path in sorted(rules_dir.rglob("*.md")):
        rel = str(path.relative_to(repo)).replace("\\", "/")
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        size = len(text.encode("utf-8"))
        paths = parse_paths(text)
        if paths is None:
            always.append({"file": rel, "size": size})
            continue
        if not paths:
            errors.append(f"{rel}: paths: is present but empty")
            continue
        scoped.append({"file": rel, "paths": paths, "size": size, "globs": compile_globs(paths)})
    always_total = sum(r["size"] for r in always)

    if args.files:
        over = 0
        for probe in args.files:
            rel = probe.replace("\\", "/")
            if os.path.isabs(rel):
                rel = str(Path(rel).resolve().relative_to(repo)).replace("\\", "/")
            hits = [r for r in scoped if matches(r, rel)]
            claude_files = claude_md_above(repo, rel)
            total = sum(r["size"] for r in hits) + always_total + sum(s for _, s in claude_files)
            flag = "  OVER BUDGET" if args.budget and total > args.budget else ""
            over += bool(flag)
            print(f"{rel}  total {total}{flag}")
            print("    rules: " + (", ".join(f"{r['file']} ({r['size']})" for r in hits) or "none"))
            if always:
                print(f"    at launch: {len(always)} rule(s) without paths ({always_total})")
            if claude_files:
                print("    CLAUDE.md: " + ", ".join(f"{name} ({size})" for name, size in claude_files))
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        if over or errors:
            sys.exit(1)
        return

    if args.shared:
        by_file = {}
        for rule in scoped:
            for f in files:
                if matches(rule, f):
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
    for rule in scoped:
        unique = set()
        zero = []
        for glob, regexes in rule["globs"]:
            hit = {f for f in files if any(m.match(f) for m in regexes)}
            unique |= hit
            if not hit:
                zero.append(glob)
        dead += len(zero)
        line = f"{rule['file']:<48} {len(unique):5d} files  {rule['size']:6d} bytes"
        if zero:
            line += "   NO HIT: " + ", ".join(zero)
        print(line)
    for rule in always:
        print(f"{rule['file']:<48}   at launch  {rule['size']:6d} bytes  (no paths: loads in every session)")
    if always:
        print(f"\n{len(always)} rule(s) load at launch in every session: {always_total} bytes")

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
