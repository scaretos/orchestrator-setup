"""Tests for analyze.py against synthetic Claude Code transcripts.

The transcripts are built in a temporary CLAUDE_CONFIG_DIR, in the shape Claude Code writes them
(one JSON object per line; assistant messages split over several lines with the same message id).
Expected values are computed by hand from the inputs, not from the script's own output.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "template", ".claude", "skills", "workflow-review", "analyze.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
sys.dont_write_bytecode = True  # no __pycache__ inside the installable template
import analyze  # noqa: E402

OPUS = "claude-opus-5-5"


def assistant(mid, time, usage, content, model=OPUS):
    return {"type": "assistant", "timestamp": time,
            "message": {"id": mid, "model": model, "usage": usage, "content": content}}


def usage(inp=0, out=0, cr=0, c5=0, c1h=0):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": c5 + c1h,
            "cache_creation": {"ephemeral_5m_input_tokens": c5, "ephemeral_1h_input_tokens": c1h}}


def user(text, time):
    return {"type": "user", "timestamp": time, "message": {"role": "user", "content": text}}


def tool_result(tid, chars, time, error=False):
    return {"type": "user", "timestamp": time, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": "x" * chars, "is_error": error}]}}


def write_jsonl(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for o in lines:
            f.write(json.dumps(o, separators=(",", ":")) + "\n")  # compact, as Claude Code writes them


class Fixture:
    """A project folder plus a config dir holding one planning and one execution session."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = os.path.join(self.tmp.name, "proj")
        os.makedirs(self.project)
        self.config = os.path.join(self.tmp.name, "config")
        pdir = os.path.join(self.config, "projects", analyze.slug(self.project))
        plan = "~/.claude/plans/demo/plan.md"

        # Planning session: /write-plan, then writes the plan file.
        write_jsonl(os.path.join(pdir, "aaaa1111.jsonl"), [
            user("<command-name>/write-plan</command-name><command-args>add csv export</command-args>", "2026-11-01T10:00:00Z"),
            assistant("p1", "2026-11-01T10:00:05Z", usage(inp=10, out=100, c1h=20000), [
                {"type": "tool_use", "id": "w1", "name": "Write",
                 "input": {"file_path": "C:\\Users\\me\\.claude\\plans\\demo\\plan.md", "content": "# Plan"}}]),
        ])

        # Execution session: 4 turns on a 1-hour cache. Turn 1 reads a 40,000-char file. Turn 2 comes 2 hours
        # later: the cache expired, nothing is read, the whole context is written again (an idle miss). Turn 3 is
        # warm. Turn 4 writes 25,000 new tokens on top of a fully read cache: a big write, not a miss.
        # Message m1 is split over two lines (same id, same usage).
        write_jsonl(os.path.join(pdir, "bbbb2222.jsonl"), [
            user(f"<command-name>/execute-plan</command-name><command-args>{plan}</command-args>", "2026-11-02T09:00:00Z"),
            assistant("m1", "2026-11-02T09:00:10Z", usage(inp=5, out=200, c1h=30000), [{"type": "thinking", "thinking": ""}]),
            assistant("m1", "2026-11-02T09:00:10Z", usage(inp=5, out=200, c1h=30000), [
                {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/src/secret_module.py"}}]),
            tool_result("r1", 40000, "2026-11-02T09:00:11Z"),
            assistant("m2", "2026-11-02T11:00:11Z", usage(inp=5, out=300, c1h=40000), [
                {"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "npm test"}}]),
            tool_result("b1", 100, "2026-11-02T11:00:20Z", error=True),
            assistant("m3", "2026-11-02T11:00:30Z", usage(inp=5, out=400, cr=40000, c1h=500), [{"type": "text", "text": "ok"}]),
            assistant("m4", "2026-11-02T11:01:00Z", usage(inp=5, out=100, cr=40505, c1h=25000), [{"type": "text", "text": "done"}]),
        ])

        # One reviewer subagent: CHANGES REQUIRED, a follow-up from the orchestrator, then PASS.
        sub = os.path.join(pdir, "bbbb2222", "subagents", "agent-x1.jsonl")
        write_jsonl(sub, [
            user("Mode: stage S1", "2026-11-02T09:01:00Z"),
            assistant("s1", "2026-11-02T09:01:05Z", usage(inp=3, out=50, c5=10000), [
                {"type": "tool_use", "id": "h1", "name": "SubagentHandback",
                 "input": {"message": "**Verdict:** CHANGES REQUIRED\n**Must fix:** x"}}]),
            {"type": "user", "isMeta": True, "origin": {"kind": "coordinator"}, "timestamp": "2026-11-02T09:03:00Z",
             "message": {"role": "user", "content": "The implementer fixed it; verify."}},
            assistant("s2", "2026-11-02T09:03:05Z", usage(inp=3, out=60, cr=10000, c5=200), [
                {"type": "tool_use", "id": "h2", "name": "SubagentHandback", "input": {"message": "**Verdict:** PASS"}}]),
        ])
        with open(sub[:-6] + ".meta.json", "w", encoding="utf-8") as f:
            json.dump({"agentType": "stage-reviewer", "description": "Review S1"}, f)

    def run(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.config, PYTHONIOENCODING="utf-8")
        out = subprocess.run([sys.executable, SCRIPT, "--project", self.project, *args], env=env,
                             capture_output=True, text=True, encoding="utf-8")
        if out.returncode != 0:
            raise AssertionError(f"analyze.py {' '.join(args)} failed:\n{out.stderr}")
        return out.stdout


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture()

    @classmethod
    def tearDownClass(cls):
        cls.fx.tmp.cleanup()

    def metrics(self, *sessions):
        return {r["role"]: r for r in json.loads(self.fx.run("metrics", *sessions, "--json"))}

    def test_runs_pairs_planning_and_execution_under_the_plan(self):
        out = self.fx.run("runs")
        block = out.split("## demo", 1)[1].split("\n## ", 1)[0]
        self.assertIn("write-plan: session `aaaa1111`", block)
        self.assertIn("execute-plan: session `bbbb2222`", block)
        self.assertIn("1 subagents", block)

    def test_metrics_main_session(self):
        m = self.metrics("bbbb2222")["main"]
        self.assertEqual(m["turns"], 4)  # m1 counted once although it spans two lines
        # m2 is the only miss: it read 0 of the 30,005 cached tokens after 2 h on a 1-hour cache.
        # m4 wrote 25,000 tokens, more than half of 40,505, but read all 40,505 from cache: not a miss.
        self.assertEqual((m["cold_rewrites"], m["cold_rewrite_tokens"], m["idle_misses"]), (1, 30005, 1))
        # only the 30,005 old tokens count, at the 1-hour write price minus the read price
        self.assertAlmostEqual(m["idle_usd"], 30005 * (8 - 0.20) / 1e6, places=12)
        self.assertEqual(m["gaps_gt5m"], 1)
        self.assertEqual(m["peak_ctx"], 65510)  # m4: 5 + 40,505 read + 25,000 written
        self.assertEqual(m["tool_errors"], 1)
        self.assertEqual(m["tools"], {"Read": 1, "Bash": 1})
        # Opus 5.5: $4 in, $20 out, $8 per M 1-hour writes, $0.20 per M reads
        usd = (20 * 4 + 1000 * 20 + 95500 * 8 + 80505 * 0.20) / 1e6
        self.assertAlmostEqual(m["usd"], usd, places=9)
        # the 40,000-char read (~10,000 tokens) is carried on turns 2 to 4 (context never shrinks)
        top = m["top_carries"][0]
        self.assertEqual((top["tool"], top["tokens"], top["turns"]), ("Read", 10000, 3))
        self.assertAlmostEqual(top["usd"], 10000 * 3 * 0.20 / 1e6, places=12)

    def test_metrics_reviewer_rounds_and_verdicts(self):
        r = self.metrics("bbbb2222")["stage-reviewer"]
        self.assertEqual(r["outcomes"], ["CHANGES REQUIRED", "PASS"])
        self.assertEqual(r["follow_ups"], 1)
        self.assertEqual(r["description"], "Review S1")

    def test_receipt(self):
        out = self.fx.run("receipt", "bbbb2222")
        lines = out.splitlines()
        self.assertTrue(all(len(l) <= analyze.W for l in lines), [l for l in lines if len(l) > analyze.W])
        main_usd = (20 * 4 + 1000 * 20 + 95500 * 8 + 80505 * 0.20) / 1e6
        sub_usd = (6 * 4 + 110 * 20 + 10200 * 5 + 10000 * 0.20) / 1e6
        total = re.search(r"TOTAL \(API-equivalent\)\s+\$([\d.,]+)", out).group(1)
        self.assertEqual(total, f"{main_usd + sub_usd:,.2f}")
        self.assertIn("1 session · 1 subagents · 6 turns", out)
        self.assertIn("Read secret_module.py", out)
        self.assertIn("Cache expired while idle: 1x", out)
        self.assertNotIn("Other cache misses", out)

    def test_receipt_redact_hides_names(self):
        out = self.fx.run("receipt", "bbbb2222", "--redact")
        self.assertNotIn("secret_module", out)
        self.assertNotIn("npm", out)

    def test_receipt_latest_and_since(self):
        self.assertIn("CLAUDE CODE RECEIPT", self.fx.run("receipt"))
        self.assertIn("LAST 36500 DAYS · 2 sessions", self.fx.run("receipt", "--since", "36500"))

    def test_receipt_svg(self):
        path = os.path.join(self.fx.tmp.name, "r.svg")
        self.fx.run("receipt", "bbbb2222", "--svg", path)
        import xml.dom.minidom
        xml.dom.minidom.parse(path)  # well-formed

    def test_timeline_and_ttl_run(self):
        transcript = os.path.join(self.fx.config, "projects", analyze.slug(self.fx.project), "bbbb2222.jsonl")
        self.assertIn("Read(/src/secret_module.py)", self.fx.run("timeline", transcript))
        self.assertIn("stage-reviewer", self.fx.run("ttl", "bbbb2222"))


class PriceTests(unittest.TestCase):
    def test_longest_prefix_wins(self):
        for model, expected in [
            ("claude-opus-5-5", (4.0, 20.0, 5.0, 8.0, 0.20)),
            ("claude-opus-5", (5.0, 25.0, 6.25, 10.0, 0.50)),
            ("claude-opus-4-8", (5.0, 25.0, 6.25, 10.0, 0.50)),
            ("claude-sonnet-5-5", (2.0, 10.0, 2.5, 4.0, 0.10)),
            ("claude-sonnet-4-6", (3.0, 15.0, 3.75, 6.0, 0.30)),
            ("claude-fable-5-2", (8.0, 40.0, 10.0, 16.0, 0.20)),
            ("claude-haiku-4-5", (1.0, 5.0, 1.25, 2.0, 0.10)),
        ]:
            with self.subTest(model=model):
                self.assertEqual(analyze.price_of(model), expected)

    def test_fast_mode_doubles(self):
        u = {"in": 1_000_000, "out": 0, "c5": 0, "c1h": 0, "cr": 0}
        self.assertEqual(sum(analyze.usd_parts(u, OPUS, fast=True).values()), 8.0)


if __name__ == "__main__":
    unittest.main()
