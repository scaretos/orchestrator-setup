#!/usr/bin/env python3
"""Mechanically move documentation sections that are already correct.

This is an optional aid for an audit, not the audit itself. It moves sections
verbatim: only heading levels are normalised to "##" and leading or trailing
blank lines are trimmed. It does not rewrite, validate or correct content.
Use it when a section is known to be right and only needs a new home; use Edit
for corrections, consolidation and new knowledge.

The config names the old documents, the new folder CLAUDE.md files and the new
.claude/rules/ files, and says which section of which old document goes where.
Nothing is written without --write. A section that is being corrected or
dropped belongs in the audit, not in this config.

Config shape:
{
  "sources": {
    "lib": "src/Lib/LIB-GUIDE.md",
    "app": "src/App/APP-GUIDE.md"
  },
  "drop": ["lib|Contents", "app|Read this when"],
  "rules": [
    {
      "file": ".claude/rules/features/invoices.md",
      "title": "Invoices",
      "paths": ["src/Lib/Invoices/**", "src/App/Views/InvoiceView.ts"],
      "parts": [
        {"source": "lib", "heading": "Invoices"},
        {"source": "app", "heading": "Invoice page", "rename": "The page in the app"}
      ]
    }
  ],
  "claude_md": [
    {
      "file": "src/Lib/CLAUDE.md",
      "title": "Lib - core library",
      "intro": "One or two lines: what this folder is and how its tests run.",
      "parts": [{"source": "lib", "heading": "Rules that apply everywhere"}],
      "scope": ["src/Lib/"],
      "rule_index": true
    }
  ]
}

A part may also be {"raw": {"title": "Topic rules", "body": "..."}} for a short
hand-written block. Every non-empty section of every source must appear in a
part or in "drop"; the script refuses to write a split that would lose one.
It also refuses to replace an existing file that is not a source (an existing
folder CLAUDE.md, say) unless --overwrite is given. Headings inside fenced
code blocks are content, not section breaks.

Usage:
  python split_docs.py config.json --repo .            # dry run: sizes only
  python split_docs.py config.json --repo . --write    # write the files

Config paths are normalized to forward slashes, so the same config works on
Windows and POSIX.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{2,3})\s+(.*)$")


def posix(value):
    """Normalize a config path separator to the form git ls-files prints."""
    return str(value).replace("\\", "/")


def read_sections(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
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
    result = {}
    for heading, body in atoms:
        if heading in result:
            raise ValueError(f"{path}: duplicate heading {heading!r}; rename one before splitting")
        result[heading] = body
    return result


def trim(lines):
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="JSON split config")
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--write", action="store_true", help="write the files (default: dry run)")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing an existing file that is not a source")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"cannot read config {args.config}: {exc}")
    sources = config.get("sources") or {}
    if not sources:
        sys.exit("config.sources is empty")

    atoms = {}
    for key, rel in sources.items():
        rel = posix(rel)
        path = repo / rel
        if not path.is_file():
            sys.exit(f"source {key!r} not found: {rel}")
        try:
            section_map = read_sections(path)
        except ValueError as exc:
            sys.exit(str(exc))
        for heading, body in section_map.items():
            atoms[(key, heading)] = body

    dropped = set()
    for entry in config.get("drop") or []:
        if "|" not in entry:
            sys.exit(f'drop entry must be "source|heading": {entry!r}')
        key, heading = entry.split("|", 1)
        if (key, heading) not in atoms:
            sys.exit(f"drop entry does not name a section: {entry!r}")
        dropped.add((key, heading))

    used = set()
    outputs = {}
    rule_index = []

    def take(part):
        if "raw" in part:
            raw = part["raw"]
            return raw.get("title", ""), trim(raw.get("body", "").split("\n"))
        key = part.get("source")
        heading = part.get("heading")
        if key is None or heading is None:
            sys.exit(f"part needs source and heading: {part!r}")
        atom = (key, heading)
        if atom not in atoms:
            sys.exit(f"part names a missing section: {key}|{heading}")
        if atom in used:
            sys.exit(f"section used twice: {key}|{heading}; give it one home")
        used.add(atom)
        title = part.get("rename") or heading
        return title, trim(atoms[atom])

    for rule in config.get("rules") or []:
        rel = posix(rule["file"])
        paths = [posix(p) for p in rule.get("paths") or []]
        if not paths:
            sys.exit(f"rule {rel} has no paths")
        lines = ["---", "paths:"]
        lines += [f'  - "{p}"' for p in paths]
        lines += ["---", "", f"# {rule['title']}", ""]
        for part in rule.get("parts") or []:
            title, body = take(part)
            if title and title != rule["title"]:
                lines += [f"## {title}", ""]
            lines += body + [""]
        outputs[rel] = "\n".join(lines).rstrip() + "\n"
        rule_index.append({"file": rel, "title": rule["title"], "paths": paths})

    for doc in config.get("claude_md") or []:
        rel = posix(doc["file"])
        lines = [f"# {doc['title']}", ""]
        if doc.get("intro"):
            lines += [doc["intro"].strip(), ""]
        for part in doc.get("parts") or []:
            title, body = take(part)
            if title and title != doc["title"]:
                lines += [f"## {title}", ""]
            lines += body + [""]
        if doc.get("rule_index"):
            scope = [posix(s) for s in doc.get("scope") or []]
            related = [
                r for r in rule_index
                if any(p.startswith(s) for p in r["paths"] for s in scope)
            ]
            lines += [
                "## Topic rules", "",
                "These load by themselves when you read or edit a matching file. To read one before touching code, open it directly.", "",
            ]
            lines += [f"- `{r['file']}` - {r['title']}" for r in related]
            lines += [""]
        outputs[rel] = "\n".join(lines).rstrip() + "\n"

    empty = {atom for atom, body in atoms.items() if not "".join(body).strip()}
    missing = sorted(set(atoms) - used - dropped - empty)
    if missing:
        print("Refusing to write: these sections have no home and are not in drop:", file=sys.stderr)
        for key, heading in missing:
            print(f"  {key}|{heading}", file=sys.stderr)
        sys.exit(1)

    if not outputs:
        sys.exit("config produced no files")

    # A file that already exists and is not a source would be replaced without
    # its content ever being checked: an existing folder CLAUDE.md or rule.
    source_files = {posix(rel) for rel in sources.values()}
    clobbered = sorted(rel for rel in outputs if (repo / rel).exists() and rel not in source_files)
    if clobbered and not args.overwrite:
        print("Refusing to write: these files exist and are not sources, so their content would be lost:",
              file=sys.stderr)
        for rel in clobbered:
            print(f"  {rel}", file=sys.stderr)
        print("Add each as a source and place its sections, or pass --overwrite after checking it.",
              file=sys.stderr)
        sys.exit(1)

    for rel, text in outputs.items():
        size = len(text.encode("utf-8"))
        print(f"{size:7d}  {rel}")
        if args.write:
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
    print(f"\n{len(outputs)} files, {sum(len(t.encode('utf-8')) for t in outputs.values())} bytes"
          + ("" if args.write else " (dry run; add --write)"))


if __name__ == "__main__":
    main()
