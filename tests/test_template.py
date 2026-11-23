"""Contract checks on the installable template: what /orchestrator-init relies on."""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "template", ".claude")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    text = read(path)
    if not text.startswith("---\n"):
        return None
    block = text.split("---\n", 2)[1]
    return {line.split(":", 1)[0]: line.split(":", 1)[1].strip()
            for line in block.splitlines() if ":" in line and not line.startswith(" ")}


class TemplateTests(unittest.TestCase):
    def test_every_placeholder_is_in_the_profile(self):
        profile = read(os.path.join(TEMPLATE, "orchestrator", "profile.md"))
        documented = set(re.findall(r"^\| ([A-Z_]+) \|", profile, re.M))
        used = set()
        for path in glob.glob(os.path.join(TEMPLATE, "**", "*.*"), recursive=True):
            if "orchestrator-init" not in path and path.endswith((".md", ".json", ".py", ".cjs")):
                used |= set(re.findall(r"\{\{([A-Z_]+)\}\}", read(path)))
        self.assertEqual(used - documented, set(), "placeholders missing from profile.md")
        self.assertEqual(documented - used, set(), "profile.md keys no file uses")

    def test_adapt_blocks_are_closed(self):
        for path in glob.glob(os.path.join(TEMPLATE, "**", "*.md"), recursive=True):
            if "orchestrator-init" in path:
                continue
            text = read(path)
            with self.subTest(path=os.path.relpath(path, ROOT)):
                self.assertEqual(text.count("<!-- ADAPT:"), text.count("<!-- /ADAPT -->"))

    def test_skills_and_agents_have_frontmatter(self):
        skills = glob.glob(os.path.join(TEMPLATE, "skills", "*", "SKILL.md"))
        agents = glob.glob(os.path.join(TEMPLATE, "agents", "*.md"))
        self.assertEqual(len(skills), 6)
        self.assertEqual(len(agents), 5)
        for path in skills + agents:
            fm = frontmatter(path)
            with self.subTest(path=os.path.relpath(path, ROOT)):
                self.assertIsNotNone(fm)
                self.assertTrue(fm.get("name"))
                self.assertTrue(fm.get("description"))
                if path in agents:
                    self.assertIn(fm.get("model"), ("opus", "sonnet", "haiku"))

    def test_skill_names_match_folders(self):
        for path in glob.glob(os.path.join(TEMPLATE, "skills", "*", "SKILL.md")):
            self.assertEqual(frontmatter(path)["name"], os.path.basename(os.path.dirname(path)))

    def test_restructure_docs_is_owner_invoked(self):
        path = os.path.join(TEMPLATE, "skills", "restructure-docs", "SKILL.md")
        self.assertEqual(frontmatter(path).get("disable-model-invocation"), "true")

    def test_restructure_docs_scripts_compile(self):
        import py_compile
        scripts = glob.glob(os.path.join(TEMPLATE, "skills", "restructure-docs", "*.py"))
        self.assertGreaterEqual(len(scripts), 4)
        for path in scripts:
            with self.subTest(path=os.path.relpath(path, ROOT)):
                py_compile.compile(path, doraise=True)

    def test_restructure_docs_scripts_are_referenced(self):
        folder = os.path.join(TEMPLATE, "skills", "restructure-docs")
        skill = read(os.path.join(folder, "SKILL.md"))
        for path in glob.glob(os.path.join(folder, "*.py")):
            self.assertIn(os.path.basename(path), skill)

    def test_restructure_docs_has_two_permission_gates(self):
        skill = read(os.path.join(TEMPLATE, "skills", "restructure-docs", "SKILL.md"))
        self.assertGreaterEqual(skill.count("AskUserQuestion"), 2)
        self.assertIn("disable-model-invocation: true", skill)

    def test_restructure_docs_steps_and_tables(self):
        skill = read(os.path.join(TEMPLATE, "skills", "restructure-docs", "SKILL.md"))
        steps = re.findall(r"^## (\d)\. ", skill, re.M)
        self.assertEqual(steps, [str(i) for i in range(8)], "steps 0-7 in order")
        for column in ("Doc class", "Content class", "Status", "Verdict", "Consumer", "Change", "Original"):
            with self.subTest(column=column):
                self.assertIn(f"| {column} |", skill)

    def test_restructure_docs_uses_its_argument_and_saves_the_audit(self):
        skill = read(os.path.join(TEMPLATE, "skills", "restructure-docs", "SKILL.md"))
        self.assertIn("$ARGUMENTS", skill)
        self.assertIn("{{PLANS_DIR}}/restructure-docs/<date>/audit.md", skill)

    def test_restructure_docs_script_calls_use_the_profile_python(self):
        skill = read(os.path.join(TEMPLATE, "skills", "restructure-docs", "SKILL.md"))
        calls = re.findall(r"^\s*(\S+) \.claude/skills/restructure-docs/\w+\.py", skill, re.M)
        self.assertTrue(calls)
        self.assertEqual(set(calls), {"{{PYTHON}}"})


if __name__ == "__main__":
    unittest.main()
