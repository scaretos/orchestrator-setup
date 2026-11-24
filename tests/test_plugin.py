"""Contract checks on the plugin packaging: manifests, versions, the install skill and the installers."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}/"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def manifest(name):
    return json.loads(read(".claude-plugin", name))


class PluginTests(unittest.TestCase):
    def test_marketplace_lists_this_repository_as_the_plugin(self):
        market = manifest("marketplace.json")
        plugin = manifest("plugin.json")
        self.assertTrue(market["owner"]["name"])
        self.assertEqual([p["name"] for p in market["plugins"]], [plugin["name"]])
        self.assertEqual(market["plugins"][0]["source"], "./")

    def test_versions_agree(self):
        version = manifest("plugin.json")["version"]
        self.assertEqual(read("template", ".claude", "orchestrator", "VERSION").strip(), version)
        first = re.search(r"^## (\S+)", read("CHANGELOG.md"), re.M).group(1)
        self.assertEqual(first, version, "newest CHANGELOG entry")

    def test_skills_path_holds_only_the_install_skill(self):
        skills = manifest("plugin.json")["skills"]
        self.assertTrue(skills.startswith("./"))
        folder = os.path.join(ROOT, skills)
        self.assertEqual(sorted(os.listdir(folder)), ["install"])
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "skills")), "a root skills/ would load as well")
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "agents")), "a root agents/ would load as well")

    def test_install_skill_is_owner_invoked_and_its_paths_exist(self):
        skill = read("plugin", "skills", "install", "SKILL.md")
        self.assertIn("\nname: install\n", skill)
        self.assertIn("\ndisable-model-invocation: true\n", skill)
        paths = set(re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)", skill))
        self.assertTrue({"install.sh", "install.ps1", "CHANGELOG.md"} <= paths)
        for rel in paths:
            with self.subTest(path=rel):
                self.assertTrue(os.path.exists(os.path.join(ROOT, rel.rstrip("."))))
        self.assertIn(".claude/skills/orchestrator-init/SKILL.md", skill)
        self.assertIn("AskUserQuestion", skill)


class InstallerTests(unittest.TestCase):
    """Both installers copy the template, keep existing files, and never overwrite the project's data."""

    DATA = ("profile.md", "ledger.md")

    def run_installer(self, target, force):
        if os.name == "nt" and shutil.which("powershell"):
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   os.path.join(ROOT, "install.ps1"), "-Target", target] + (["-Force"] if force else [])
            yield "install.ps1", subprocess.run(cmd, capture_output=True, text=True)
        bash = shutil.which("bash")
        if bash:
            cmd = [bash, os.path.join(ROOT, "install.sh").replace("\\", "/"), target.replace("\\", "/")]
            yield "install.sh", subprocess.run(cmd + (["--force"] if force else []), capture_output=True, text=True)

    def check(self, force):
        ran = 0
        for name in ("install.sh", "install.ps1"):
            target = tempfile.mkdtemp()
            try:
                orch = os.path.join(target, ".claude", "orchestrator")
                os.makedirs(orch)
                for data in self.DATA + ("VERSION",):
                    with open(os.path.join(orch, data), "w", encoding="utf-8") as f:
                        f.write("project\n")
                for installer, result in self.run_installer(target, force):
                    if installer != name:
                        continue
                    ran += 1
                    with self.subTest(installer=installer, force=force):
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertTrue(os.path.isfile(os.path.join(target, ".claude", "skills", "write-plan", "SKILL.md")))
                        for data in self.DATA:
                            self.assertEqual(read_file(os.path.join(orch, data)), "project\n", data)
                        expected = read("template", ".claude", "orchestrator", "VERSION") if force else "project\n"
                        self.assertEqual(read_file(os.path.join(orch, "VERSION")), expected)
            finally:
                shutil.rmtree(target, ignore_errors=True)
        if not ran:
            self.skipTest("no bash or powershell on PATH")

    def test_keeps_existing_files_without_force(self):
        self.check(force=False)

    def test_force_overwrites_all_but_the_project_data(self):
        self.check(force=True)


def read_file(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


if __name__ == "__main__":
    unittest.main()
