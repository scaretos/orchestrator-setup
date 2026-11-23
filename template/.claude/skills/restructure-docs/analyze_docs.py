#!/usr/bin/env python3
"""Audit aid: inventory the documentation a codebase asks agents to read.

For every document, print its size and one line per section: the section's
size and the repository files its backticked names resolve to. That mapping is
the input for deciding what to verify, correct, keep or move into folder
CLAUDE.md files and path-scoped .claude/rules/ files.

Usage:
  python analyze_docs.py --repo . CLAUDE.md docs/GUIDE.md src/Lib/LIB-CLAUDE.md
  python analyze_docs.py --repo . --json docs/*.md
  python analyze_docs.py --repo . --section "Steps" docs/GUIDE.md
  python analyze_docs.py --repo . --history 6

--section lists the paragraphs of one section with their sizes and references,
for a section that holds several independent topics and needs paragraph-level
destinations. Paths are normalized to forward slashes so the inventory works on
Windows and POSIX. Only reads; changes nothing.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{2,3})\s+(.*)$")
BACKTICK = re.compile(r"`([^`]+)`")


def git_files(repo: Path, excludes):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-co", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(f"git ls-files failed in {repo}: {exc}")
    return [
        f.replace("\\", "/") for f in out.splitlines()
        if f and not any(f.replace("\\", "/").startswith(prefix) for prefix in excludes)
    ]


def build_resolver(files):
    by_base = {}
    for f in files:
        by_base.setdefault(os.path.basename(f), []).append(f)

    def resolve(token: str):
        token = token.replace("\\", "/").replace("(", "").replace(")", "").strip()
        if not token or re.search(r"\s", token):
            return []
        if token.endswith("/**"):
            token = token[:-3].rstrip("/")
        if token.startswith("./"):
            token = token[2:]
        hits = [f for f in files if f == token or f.endswith("/" + token)]
        if "/" in token:
            prefix = token.rstrip("/") + "/"
            hits += [f for f in files if f.startswith(prefix)]
        if hits:
            return hits
        # A bare class or file name is the common form in guides.
        base = os.path.basename(token)
        if base in by_base:
            return by_base[base]
        if not base.endswith((".cs", ".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs", ".cpp", ".h", ".xaml", ".json", ".md")):
            for ext in (".cs", ".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs", ".cpp", ".h", ".xaml"):
                if base + ext in by_base:
                    return by_base[base + ext]
        return []

    return resolve


def sections(text: str):
    """Yield (heading, body) atoms. Every ## or ### heading outside a code fence starts a new atom."""
    atoms = [("(top)", [])]
    fenced = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        match = None if fenced else HEADING.match(line)
        if match:
            atoms.append((match.group(2).strip(), []))
        else:
            atoms[-1][1].append(line)
    for heading, body in atoms:
        yield heading, "\n".join(body)


def paragraphs(body: str):
    """Split a section body into blank-line separated paragraphs.

    A fenced code block stays in one paragraph even when it contains blank lines.
    """
    result = []
    current = []
    fenced = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            current.append(line)
            continue
        if not fenced and not line.strip():
            if current:
                result.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        result.append("\n".join(current))
    return result


def history(repo: Path, months: int, excludes, depth: int = 2, top: int = 15):
    """Which kinds of change recur: commits grouped by the folders they touch together."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"--since={months} months ago", "--no-merges",
             "--name-only", "--format=@@%h %s"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(f"git log failed in {repo}: {exc}")
    commits = []
    for line in out.splitlines():
        if line.startswith("@@"):
            commits.append((line[2:], []))
        elif line.strip() and commits:
            f = line.strip().replace("\\", "/")
            if not any(f.startswith(prefix) for prefix in excludes):
                commits[-1][1].append(f)
    file_counts, shapes = {}, {}
    for header, changed in commits:
        for f in set(changed):
            file_counts[f] = file_counts.get(f, 0) + 1
        folders = tuple(sorted({"/".join(f.split("/")[:depth]) if "/" in f else "(root)" for f in changed}))
        if len(folders) > 1:
            shapes.setdefault(folders, []).append(header)
    print(f"{len(commits)} commits in the last {months} months\n")
    print("Folder sets changed together most often (a recurring kind of change; candidates for a checklist skill):")
    for folders, headers in sorted(shapes.items(), key=lambda kv: -len(kv[1]))[:top]:
        print(f"{len(headers):5d}  {' + '.join(folders)}")
        for header in headers[:3]:
            print(f"         e.g. {header[:100]}")
    print("\nFiles changed in the most commits:")
    for f, count in sorted(file_counts.items(), key=lambda kv: -kv[1])[:top]:
        print(f"{count:5d}  {f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=int, metavar="MONTHS",
                        help="instead of documents: the folder sets and files that changed together most often")
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--max-refs", type=int, default=12, help="references printed per section")
    parser.add_argument("--section", help="print the paragraphs of this heading instead of the section table")
    parser.add_argument(
        "--exclude",
        default=".git/,.claude/worktrees/,node_modules/,vendor/,third_party/,third-party/,.venv/,dist/,build/,bin/,obj/,target/",
        help="comma-separated path prefixes treated as generated or vendored",
    )
    parser.add_argument("docs", nargs="*", help="documents to analyse, relative to the repo")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    excludes = tuple(x.strip() for x in args.exclude.split(",") if x.strip())
    if args.history:
        history(repo, args.history, excludes)
        return
    if not args.docs:
        parser.error("name the documents to analyse, or pass --history MONTHS")
    files = git_files(repo, excludes)
    resolve = build_resolver(files)

    if args.section:
        if len(args.docs) != 1:
            sys.exit("--section takes exactly one document")
        path = (repo / args.docs[0]).resolve()
        if not path.is_file():
            sys.exit(f"not a file: {args.docs[0]}")
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        body = None
        for heading, candidate in sections(text):
            if heading.lower() == args.section.lower():
                body = candidate
                break
        if body is None:
            sys.exit(f"no section named {args.section!r} in {args.docs[0]}")
        items = []
        for index, paragraph in enumerate(paragraphs(body), 1):
            refs = set()
            for token in BACKTICK.findall(paragraph):
                refs.update(resolve(token))
            items.append({
                "index": index,
                "bytes": len(paragraph.encode("utf-8")),
                "refs": sorted(refs),
                "text": paragraph,
            })
        if args.json:
            print(json.dumps(
                {"file": args.docs[0], "section": args.section, "paragraphs": items},
                indent=2, ensure_ascii=False,
            ))
            return
        print(f"=== {args.docs[0]} :: {args.section}")
        for item in items:
            first = item["text"].split("\n", 1)[0]
            print(f"{item['bytes']:7d}  [{item['index']}] {first[:110]}")
            if item["refs"]:
                shown = ", ".join(item["refs"][:args.max_refs])
                more = f" (+{len(item['refs']) - args.max_refs})" if len(item["refs"]) > args.max_refs else ""
                print(f"         {shown}{more}")
        return

    report = {"repo": str(repo), "documents": [], "existing": {}}

    rules_dir = repo / ".claude" / "rules"
    report["existing"]["rules"] = sorted(
        str(p.relative_to(repo)).replace("\\", "/")
        for p in rules_dir.rglob("*.md")
    ) if rules_dir.is_dir() else []
    report["existing"]["claude_md"] = sorted(
        str(p.relative_to(repo)).replace("\\", "/")
        for p in repo.rglob("CLAUDE.md")
        if not any(
            str(p.relative_to(repo)).replace("\\", "/").startswith(prefix)
            for prefix in excludes
        )
    )

    for doc in args.docs:
        path = (repo / doc).resolve()
        if not path.is_file():
            sys.exit(f"not a file: {doc}")
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        entry = {"file": doc, "bytes": len(text.encode("utf-8")), "sections": []}
        for heading, body in sections(text):
            refs = set()
            for token in BACKTICK.findall(body):
                refs.update(resolve(token))
            entry["sections"].append({
                "heading": heading,
                "bytes": len(body.encode("utf-8")),
                "refs": sorted(refs),
            })
        report["documents"].append(entry)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print(f"repository: {repo}")
    if report["existing"]["rules"]:
        print(f"existing rules: {len(report['existing']['rules'])}")
    else:
        print("existing rules: none")
    print(f"existing CLAUDE.md files: {len(report['existing']['claude_md'])}")
    for entry in report["documents"]:
        print(f"\n=== {entry['file']} ({entry['bytes']} bytes)")
        for section in entry["sections"]:
            print(f"{section['bytes']:7d}  {section['heading']}")
            refs = section["refs"]
            if refs:
                shown = ", ".join(refs[:args.max_refs])
                more = f" (+{len(refs) - args.max_refs})" if len(refs) > args.max_refs else ""
                print(f"         {shown}{more}")
    print("\nRead the sizes and references: a section with no file references is usually a cross-cutting")
    print("topic; a section whose references cluster in one folder is usually that folder's CLAUDE.md.")


if __name__ == "__main__":
    main()
