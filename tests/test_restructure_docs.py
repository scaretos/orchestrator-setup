"""Behaviour of the /restructure-docs helper scripts on a throwaway git repository."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "template", ".claude", "skills", "restructure-docs")


def write(repo, rel, text):
    path = os.path.join(repo, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run(script, *args, cwd):
    return subprocess.run(
        [sys.executable, "-I", os.path.join(SCRIPTS, script), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


class RestructureDocsScripts(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="rd-test-")
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "test")
        write(self.repo, "src/api/a.ts", "x\n")
        write(self.repo, "src/api/b.tsx", "x\n")
        write(self.repo, "lib/c.py", "x\n")
        write(self.repo, "other/d.txt", "x\n")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def rule(self, name, frontmatter, body="# rule\n"):
        write(self.repo, f".claude/rules/{name}.md", (f"---\n{frontmatter}\n---\n" if frontmatter else "") + body)

    # check_rules.py

    def test_brace_glob_is_not_dead(self):
        self.rule("ts", 'paths:\n  - "src/**/*.{ts,tsx}"')
        result = run("check_rules.py", "--repo", ".", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 files", result.stdout)

    def test_inline_and_comma_separated_paths(self):
        self.rule("inline", "paths: [src/**, lib/**]")
        self.rule("comma", "paths: src/api/*.ts, lib/*.py")
        self.rule("single", 'paths: "lib/**"')
        result = run("check_rules.py", "--repo", ".", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("ERROR", result.stderr)

    def test_rule_without_paths_loads_at_launch(self):
        self.rule("always", None, "# always\n")
        self.rule("lib", 'paths:\n  - "lib/**"')
        result = run("check_rules.py", "--repo", ".", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("at launch", result.stdout)
        probe = run("check_rules.py", "--repo", ".", "other/d.txt", cwd=self.repo)
        self.assertIn("rules: none", probe.stdout)
        self.assertIn("1 rule(s) without paths", probe.stdout)

    def test_dead_glob_and_empty_paths_fail(self):
        self.rule("dead", 'paths:\n  - "nowhere/**"')
        result = run("check_rules.py", "--repo", ".", cwd=self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO HIT: nowhere/**", result.stdout)
        os.remove(os.path.join(self.repo, ".claude", "rules", "dead.md"))
        self.rule("empty", "paths:")
        self.assertEqual(run("check_rules.py", "--repo", ".", cwd=self.repo).returncode, 1)

    def test_probe_budget(self):
        self.rule("big", 'paths:\n  - "lib/**"', "# big\n" + "x" * 500 + "\n")
        within = run("check_rules.py", "--repo", ".", "--budget", "10000", "lib/c.py", cwd=self.repo)
        self.assertEqual(within.returncode, 0, within.stdout)
        over = run("check_rules.py", "--repo", ".", "--budget", "100", "lib/c.py", cwd=self.repo)
        self.assertEqual(over.returncode, 1)
        self.assertIn("OVER BUDGET", over.stdout)

    def test_shared_files(self):
        self.rule("one", 'paths:\n  - "src/**"')
        self.rule("two", 'paths:\n  - "src/api/a.ts"')
        result = run("check_rules.py", "--repo", ".", "--shared", cwd=self.repo)
        self.assertIn("src/api/a.ts", result.stdout)
        self.assertIn("1 file(s) load more than one rule", result.stdout)

    # analyze_docs.py and split_docs.py

    GUIDE = "# Guide\n\n## Build\n\nRun it:\n\n```bash\n## a comment, not a heading\nmake\n```\n\n## Traps\n\n- `lib/c.py` is fragile\n"

    def test_heading_inside_a_fence_is_content(self):
        write(self.repo, "GUIDE.md", self.GUIDE)
        result = run("analyze_docs.py", "--repo", ".", "--json", "GUIDE.md", cwd=self.repo)
        headings = [s["heading"] for s in json.loads(result.stdout)["documents"][0]["sections"]]
        self.assertEqual(headings, ["(top)", "Build", "Traps"])
        self.assertIn("lib/c.py", result.stdout)

    def split_config(self, target):
        config = {
            "sources": {"g": "GUIDE.md"},
            "drop": ["g|(top)"],
            "rules": [{"file": ".claude/rules/build.md", "title": "Build", "paths": ["lib/**"],
                       "parts": [{"source": "g", "heading": "Build"}]}],
            "claude_md": [{"file": target, "title": "Lib", "parts": [{"source": "g", "heading": "Traps"}]}],
        }
        path = os.path.join(self.repo, "..", os.path.basename(self.repo) + "-split.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f)
        self.addCleanup(os.remove, path)
        return path

    def test_split_moves_a_fenced_block_whole(self):
        write(self.repo, "GUIDE.md", self.GUIDE)
        config = self.split_config("lib/CLAUDE.md")
        result = run("split_docs.py", config, "--repo", ".", "--write", cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(self.repo, ".claude", "rules", "build.md"), encoding="utf-8") as f:
            rule = f.read()
        self.assertEqual(rule.count("```"), 2)
        self.assertIn("make", rule)
        strict = run("verify_move.py", "loss", "--strict", "--old", "GUIDE.md",
                     "--new", ".claude/rules/build.md", "lib/CLAUDE.md", cwd=self.repo)
        self.assertEqual(strict.returncode, 0, strict.stdout)

    def test_split_refuses_to_overwrite_an_existing_file(self):
        write(self.repo, "GUIDE.md", self.GUIDE)
        write(self.repo, "lib/CLAUDE.md", "# Existing\n\nA local fact\n")
        config = self.split_config("lib/CLAUDE.md")
        refused = run("split_docs.py", config, "--repo", ".", "--write", cwd=self.repo)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("lib/CLAUDE.md", refused.stderr)
        with open(os.path.join(self.repo, "lib", "CLAUDE.md"), encoding="utf-8") as f:
            self.assertIn("A local fact", f.read())
        forced = run("split_docs.py", config, "--repo", ".", "--write", "--overwrite", cwd=self.repo)
        self.assertEqual(forced.returncode, 0, forced.stderr)

    # verify_move.py

    def test_verify_move_reads_old_from_base(self):
        write(self.repo, "CLAUDE.md", "# Root\n\nKeep `make test` fast\nThe port is 8080\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        write(self.repo, "CLAUDE.md", "# Root\n\nKeep `make test` fast\n")
        loss = run("verify_move.py", "loss", "--strict", "--base", "HEAD", "--old", "CLAUDE.md",
                   "--new", "CLAUDE.md", cwd=self.repo)
        self.assertEqual(loss.returncode, 1)
        self.assertIn("The port is 8080", loss.stdout)
        facts = run("verify_move.py", "facts", "--base", "HEAD", "--old", "CLAUDE.md",
                    "--new", "CLAUDE.md", cwd=self.repo)
        self.assertIn("8080", facts.stdout)


if __name__ == "__main__":
    unittest.main()
