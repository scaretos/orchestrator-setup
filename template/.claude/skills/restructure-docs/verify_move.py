#!/usr/bin/env python3
"""Review what a documentation change removed.

  loss   Compare every non-blank, non-heading line of the old documents with
         the new files, counting occurrences. Prints the lines that no longer
         appear verbatim. With --strict it exits 1 when any are missing; use
         that only for a section that was supposed to move unchanged.
  facts  For each line that no longer appears verbatim, find its closest new
         line and print the words that appear nowhere in the new files. A
         disappeared identifier, number, path, command or quoted name is a fact
         to restore or to justify as wrong, redundant or irrelevant.

This is a review aid, not proof that knowledge survived. A rewrite is allowed
to drop lines; it is not allowed to drop a fact without a reason.

Usage:
  python verify_move.py loss  --old old/A.md old/B.md --new A/CLAUDE.md .claude/rules/*.md
  python verify_move.py loss --strict --old old/A.md --new A/CLAUDE.md
  python verify_move.py facts --base <commit> --old CLAUDE.md docs/GUIDE.md --new CLAUDE.md .claude/rules/*.md

With --base, every --old path is read from that commit (git show), so a file
that was edited in place, such as the root CLAUDE.md, or a guide already
removed with git rm, is compared in its original form. Run it from the
repository root. Path arguments are normalized, so `/` and `\\` both work on
Windows and POSIX.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z0-9_.%<>*/:-]{3,}")


def as_path(value):
    """Normalize a CLI path separator before constructing a Path."""
    return Path(str(value).replace("\\", "/"))


BASE = None  # commit the old documents are read from (--base)


def read_text(path: Path, from_base=False):
    if from_base and BASE:
        rel = path.as_posix()
        rel = rel[2:] if rel.startswith("./") else rel
        spec = f"{BASE}:./{rel}"
        try:
            raw = subprocess.run(["git", "show", spec], capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            sys.exit(f"cannot read {spec}: {exc}")
        return raw.decode("utf-8-sig", errors="replace")
    return path.read_text(encoding="utf-8-sig", errors="replace")


def read_lines(path: Path, skip_frontmatter=False, from_base=False):
    text = read_text(path, from_base)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if skip_frontmatter and lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1)
            lines = lines[end + 1:]
        except ValueError:
            pass
    return lines


def content_lines(lines):
    for line in lines:
        if not line.strip():
            continue
        if re.match(r"^#{1,6}\s", line):
            continue
        yield line.rstrip()


def bag(paths, skip_frontmatter=False, from_base=False):
    counts = {}
    for path in paths:
        for line in content_lines(read_lines(path, skip_frontmatter, from_base)):
            counts[line] = counts.get(line, 0) + 1
    return counts


def tokens(text):
    return {match.group(0).lower().rstrip(".,;:") for match in TOKEN.finditer(text)}


def missing_lines(old_paths, new_paths):
    old = bag(old_paths, from_base=True)
    new = bag(new_paths, skip_frontmatter=True)
    missing = []
    for line, count in old.items():
        difference = count - new.get(line, 0)
        if difference > 0:
            missing.append((line, difference))
    return missing, old, new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("loss", "facts"))
    parser.add_argument("--old", nargs="+", required=True, help="old documents")
    parser.add_argument("--new", nargs="+", required=True, help="new files")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when an old line no longer appears verbatim (use only for an unchanged move)",
    )
    parser.add_argument("--base", help="read every --old path from this commit instead of the working tree")
    args = parser.parse_args()

    global BASE
    BASE = args.base
    old_paths = [as_path(p) for p in args.old]
    new_paths = [as_path(p) for p in args.new]
    for path in new_paths + ([] if BASE else old_paths):
        if not path.is_file():
            sys.exit(f"not a file: {path}")

    missing, _, _ = missing_lines(old_paths, new_paths)
    if not missing:
        print("every old content line appears verbatim in the new files")
        return

    if args.mode == "loss":
        for line, count in missing:
            print(f"NOT VERBATIM x{count}: {line[:200]}")
        print(f"\n{sum(c for _, c in missing)} line(s) no longer appear verbatim")
        if args.strict:
            sys.exit(1)
        return

    all_new = "\n".join(
        line
        for path in new_paths
        for line in content_lines(read_lines(path, skip_frontmatter=True))
    )
    new_lines = [
        (str(path), line)
        for path in new_paths
        for line in content_lines(read_lines(path, skip_frontmatter=True))
    ]
    new_tokens = tokens(all_new)
    for line, _ in missing:
        old_tokens = tokens(line)
        best = None
        best_score = 0.0
        for path, candidate in new_lines:
            overlap = len(old_tokens & tokens(candidate))
            score = overlap / len(old_tokens) if old_tokens else 0.0
            if score > best_score:
                best_score = score
                best = (path, candidate)
        candidate_tokens = tokens(best[1]) if best else set()
        dropped = old_tokens - candidate_tokens
        gone = sorted(token for token in dropped if token not in new_tokens)
        print(f"[{best_score * 100:3.0f}%] {best[0] if best else '-'} :: {line[:140]}")
        if gone:
            print("       absent from all new files: " + " ".join(gone))


if __name__ == "__main__":
    main()
