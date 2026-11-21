#!/usr/bin/env python3
"""Measure /write-plan and /execute-plan runs from Claude Code transcripts.

Standard library only. Reads ~/.claude/projects/<project-slug>*/ (or $CLAUDE_CONFIG_DIR/projects).

  analyze.py runs     [--project DIR] [--limit N]       sessions that ran the workflow, grouped by plan
  analyze.py metrics  SESSION [SESSION ...] [--json]     per-agent and per-role cost of sessions + their subagents
  analyze.py timeline FILE [--from N] [--to N] [--grep RE]   one line per turn of one transcript
  analyze.py ttl      SESSION [SESSION ...]              what-if: subagents on a 1-hour instead of a 5-minute cache

SESSION is a session id (prefix is enough), a .jsonl path, or a session directory.

Cost is in relative units, not money: input tokens of the strongest model = 1. Defaults follow
Anthropic's published price ratios (cache write 5m 1.25x, 1h 2x, cache read 0.1x, output 5x;
Sonnet 0.6x and Haiku 0.2x of Opus). Override with --weights / --model-weights if they change.
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN_WEIGHTS = {"in": 1.0, "c5": 1.25, "c1h": 2.0, "cr": 0.1, "out": 5.0}
MODEL_WEIGHTS = {"opus": 1.0, "fable": 1.0, "sonnet": 0.6, "haiku": 0.2}
COMMANDS = ("write-plan", "execute-plan", "workflow-review")


# ---------- locating transcripts ----------

def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def project_dirs(project, extra=()):
    base = os.path.join(config_dir(), "projects")
    s = slug(project)
    dirs = [d for d in glob.glob(os.path.join(base, s + "*"))
            if os.path.basename(d) == s or os.path.basename(d).startswith(s + "--claude-worktrees-")]
    for e in extra:
        dirs += glob.glob(os.path.join(base, slug(e) + "*"))
    return sorted(set(d for d in dirs if os.path.isdir(d)))


def resolve_session(ref, project, extra=()):
    """Return (main_jsonl or None, [subagent jsonl])."""
    if os.path.isfile(ref):
        main = ref
    elif os.path.isdir(ref):
        main = ref.rstrip("/\\") + ".jsonl"
        main = main if os.path.isfile(main) else None
    else:
        hits = []
        for d in project_dirs(project, extra):
            hits += glob.glob(os.path.join(d, ref + "*.jsonl"))
        hits = [h for h in hits if ".orphaned-" not in h]
        if not hits:
            sys.exit(f"no session matching {ref!r} under {config_dir()}/projects for {project}")
        if len(hits) > 1:
            sys.exit(f"{ref!r} is ambiguous: " + ", ".join(os.path.basename(h) for h in hits))
        main = hits[0]
    stem = (main[:-6] if main else ref.rstrip("/\\"))
    subs = sorted(glob.glob(os.path.join(stem, "subagents", "agent-*.jsonl")))
    return main, subs


# ---------- reading one transcript ----------

def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def is_tool_result(content):
    return isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def model_weight(model, mw):
    m = (model or "").lower()
    for k, w in mw.items():
        if k in m:
            return w
    return 1.0


def load_meta(path):
    mp = path[:-6] + ".meta.json"
    if os.path.isfile(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                return json.load(f)
        except ValueError:
            pass
    return {}


def parse(path):
    """Turns (one per API message, deduplicated by message id) plus tool uses, results and user prompts."""
    turns, order = {}, []
    tools, results, prompts = [], [], []
    for o in read_lines(path):
        t = o.get("type")
        if t == "attachment":
            att = o.get("attachment") or {}
            if att.get("type") == "nested_memory":  # a CLAUDE.md or rule file loaded by path
                prompts.append({"turn": len(order), "time": o.get("timestamp"), "text": "", "rule": att.get("path")})
            continue
        if t == "user":
            if o.get("isMeta") and (o.get("origin") or {}).get("kind") == "coordinator":
                # a SendMessage follow-up from the orchestrator
                prompts.append({"turn": len(order), "time": o.get("timestamp"), "text": text_of(o["message"].get("content"))})
                continue
            c = o.get("message", {}).get("content")
            if is_tool_result(c):
                for x in c:
                    if isinstance(x, dict) and x.get("type") == "tool_result":
                        body = x.get("content")
                        size = len(text_of(body)) if isinstance(body, list) else len(str(body or ""))
                        results.append({"id": x.get("tool_use_id"), "error": bool(x.get("is_error")),
                                        "chars": size, "turn": len(order)})
            elif not o.get("isMeta"):
                txt = text_of(c)
                if txt.strip():
                    prompts.append({"turn": len(order), "time": o.get("timestamp"), "text": txt})
        elif t == "assistant":
            m = o.get("message", {})
            if m.get("model") == "<synthetic>":
                continue
            mid = m.get("id") or o.get("uuid")
            if mid not in turns:
                order.append(mid)
                turns[mid] = {"usage": m.get("usage") or {}, "model": m.get("model"),
                              "time": o.get("timestamp"), "tools": [], "skill": o.get("attributionSkill")}
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    use = {"id": c.get("id"), "name": c.get("name"), "input": c.get("input") or {},
                           "turn": len(order)}
                    turns[mid]["tools"].append(use)
                    tools.append(use)
    return [turns[k] for k in order], tools, results, prompts


def usage_split(u):
    cc = u.get("cache_creation") or {}
    total_write = u.get("cache_creation_input_tokens", 0) or 0
    c1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    c5 = cc.get("ephemeral_5m_input_tokens", 0) or 0
    if not cc:
        c5 = total_write
    return {"in": u.get("input_tokens", 0) or 0, "c5": c5, "c1h": c1h,
            "cr": u.get("cache_read_input_tokens", 0) or 0, "out": u.get("output_tokens", 0) or 0,
            "write": total_write}


def command_class(cmd, classes):
    return [name for name, rx in classes if rx.search(cmd)]


def analyze_file(path, tw, mw, classes):
    turns, tools, results, prompts = parse(path)
    meta = load_meta(path)
    role = meta.get("agentType") or "main"
    tot = collections.Counter()
    units = 0.0
    peak = 0
    prev_t = prev_ctx = None
    gaps5 = gaps60 = 0
    cold = []  # (turn, tokens written, gap seconds)
    models = collections.Counter()
    for i, tr in enumerate(turns, 1):
        u = usage_split(tr["usage"])
        w = model_weight(tr["model"], mw)
        models[tr["model"]] += 1
        units += w * sum(tw[k] * u[k] for k in tw)
        for k in ("in", "c5", "c1h", "cr", "out"):
            tot[k] += u[k]
        ctx = u["in"] + u["cr"] + u["write"]
        peak = max(peak, ctx)
        t = ts(tr["time"])
        gap = (t - prev_t).total_seconds() if (t and prev_t) else 0
        if gap > 300:
            gaps5 += 1
        if gap > 3600:
            gaps60 += 1
        if prev_ctx and prev_ctx > 20_000 and u["write"] > 0.5 * prev_ctx:
            cold.append((i, u["write"], int(gap)))
        prev_ctx, prev_t = ctx, (t or prev_t)

    tool_count = collections.Counter(x["name"] for x in tools)
    read_keys = collections.Counter()
    plan_reads = md_reads = 0
    for x in tools:
        if x["name"] == "Read":
            fp = str(x["input"].get("file_path", ""))
            read_keys[(fp.lower(), x["input"].get("offset"), x["input"].get("limit"))] += 1
            if fp.endswith(".md"):
                md_reads += 1
            if fp.replace("\\", "/").endswith("/plan.md"):
                plan_reads += 1
    dup_reads = sum(n - 1 for n in read_keys.values() if n > 1)
    first_edit = next((x["turn"] for x in tools if x["name"] in ("Edit", "Write", "MultiEdit", "NotebookEdit")), None)
    cmd_classes = collections.Counter()
    for x in tools:
        if x["name"] in ("Bash", "PowerShell"):
            for c in command_class(str(x["input"].get("command", "")), classes):
                cmd_classes[c] += 1
    big_results = sum(1 for r in results if r["chars"] > 20_000)
    # Reports: each SubagentHandback is one round's report; older transcripts end with plain text instead.
    reports = [str(x["input"].get("message", "")) for x in tools if x["name"] == "SubagentHandback"]
    if not reports:
        for tr_text in reversed([text_of(o.get("message", {}).get("content")) for o in read_lines(path)
                                 if o.get("type") == "assistant"]):
            if tr_text.strip():
                reports = [tr_text]
                break
    outcomes = []
    for rep in reports:
        m = re.search(r"Verdict:?\**:?\s*(READY|REVISE|PASS|CHANGES REQUIRED)", rep) or \
            re.search(r"Status:?\**:?\s*(DONE|BLOCKED)", rep)
        if m:
            outcomes.append(m.group(1))
    follow_ups = [p for p in prompts if p.get("text") and not p.get("rule")]
    rules = [p["rule"] for p in prompts if p.get("rule")]
    t0, t1 = (ts(turns[0]["time"]), ts(turns[-1]["time"])) if turns else (None, None)
    return {
        "file": os.path.basename(path), "first_time": turns[0]["time"] if turns else None, "role": role, "description": meta.get("description", ""),
        "requested_model": meta.get("model"), "models": dict(models),
        "turns": len(turns), "units": units, "tokens": dict(tot), "peak_ctx": peak,
        "cold_rewrites": len(cold), "cold_rewrite_tokens": sum(c[1] for c in cold),
        "cold_detail": cold[:8], "gaps_gt5m": gaps5, "gaps_gt1h": gaps60,
        "minutes": round((t1 - t0).total_seconds() / 60, 1) if t0 and t1 else 0,
        "follow_ups": max(0, len(follow_ups) - 1), "rules_loaded": len(rules),
        "tool_errors": sum(1 for r in results if r["error"]),
        "big_tool_results": big_results, "reads": tool_count.get("Read", 0), "md_reads": md_reads,
        "plan_reads": plan_reads, "dup_reads": dup_reads, "first_edit_turn": first_edit,
        "single_call_turn_share": round(sum(1 for t in turns if len(t["tools"]) == 1) / len(turns), 2) if turns else 0,
        "commands": dict(cmd_classes), "tools": dict(tool_count.most_common(10)),
        "outcomes": outcomes,
    }


# ---------- commands ----------

DEFAULT_CLASSES = [
    ("build", r"\b(dotnet|cargo|go|gradle|mvn|cmake|npm run|pnpm|yarn)\s+(\S+\s+)?build\b|\bmsbuild\b|\btsc\b|^\s*make\b"),
    ("test", r"\b(dotnet test|pytest|cargo test|go test|npm (run )?test|pnpm test|yarn test|jest|vitest|mvn test|gradle test|rspec|phpunit)\b"),
    ("gate", r"gate\.(ps1|sh)|\bgate\b"),
    ("git", r"\bgit (diff|log|show|status|blame)\b"),
    ("sleep/poll", r"Start-Sleep|\bsleep \d|Get-Content .*-Wait|tail -f"),
]


def cmd_metrics(a):
    tw = dict(TOKEN_WEIGHTS, **json.loads(a.weights)) if a.weights else TOKEN_WEIGHTS
    mw = dict(MODEL_WEIGHTS, **json.loads(a.model_weights)) if a.model_weights else MODEL_WEIGHTS
    classes = [(n, re.compile(r, re.I)) for n, r in DEFAULT_CLASSES]
    rows = []
    for ref in a.sessions:
        main, subs = resolve_session(ref, a.project, a.extra_dir)
        for p in ([main] if main else []) + subs:
            r = analyze_file(p, tw, mw, classes)
            r["session"] = os.path.basename(main or ref)[:8]
            rows.append(r)
    if a.json:
        print(json.dumps(rows, indent=1, default=str))
        return
    total = sum(r["units"] for r in rows) or 1
    print(f"# Metrics: {len(rows)} transcripts, {total / 1e6:.2f}M units\n")
    print("Units: input of the strongest model = 1; see analyze.py header. Measured from transcripts.\n")
    roles = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        g = roles[r["role"]]
        g["agents"] += 1; g["turns"] += r["turns"]; g["units"] += r["units"]
        g["cold"] += r["cold_rewrite_tokens"]; g["follow_ups"] += r["follow_ups"]
    print("| role | agents | turns | units (M) | share | cold-rewrite tokens | follow-up rounds |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for role, g in sorted(roles.items(), key=lambda kv: -kv[1]["units"]):
        print(f"| {role} | {g['agents']} | {g['turns']} | {g['units'] / 1e6:.2f} | {g['units'] / total:.0%} | {g['cold']:,} | {g['follow_ups']} |")
    tok = collections.Counter()
    for r in rows:
        w = model_weight(next(iter(r["models"]), ""), mw)
        for k in tw:
            tok[k] += w * tw[k] * r["tokens"].get(k, 0)
    tt = sum(tok.values()) or 1
    print("\nCost split: " + ", ".join(f"{k} {v / tt:.0%}" for k, v in
                                      sorted(tok.items(), key=lambda kv: -kv[1])) +
          "  (cr = cache read, c5/c1h = cache write 5 min / 1 h, out = output)\n")
    print("Columns: cold rewrites = turns that wrote more than half the previous context again (expired cache);"
          " rounds = follow-up messages after the first prompt; rules = CLAUDE.md/rule files loaded by path;"
          " outcomes = verdict or status of each report, in order.\n")
    print("| session | agent | role | model | turns | units (M) | peak ctx | cold rewrites | gaps >5m/>1h | min | rounds | first edit | reads (dup) | plan reads | rules | errors | outcomes |")
    print("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    rows.sort(key=lambda r: (r["session"], r["role"] != "main", r["first_time"] or ""))
    for r in rows:
        model = ",".join(re.sub(r"^claude-", "", m or "?") for m in r["models"])
        desc = (r["description"] or "(main) " + r["file"][:8])[:40]
        print(f"| {r['session']} | {desc} | {r['role']} | {model} | {r['turns']} | {r['units'] / 1e6:.2f} | "
              f"{r['peak_ctx'] // 1000}k | {r['cold_rewrites']} ({r['cold_rewrite_tokens'] // 1000}k) | "
              f"{r['gaps_gt5m']}/{r['gaps_gt1h']} | {r['minutes']} | {r['follow_ups']} | {r['first_edit_turn'] or '-'} | "
              f"{r['reads']} ({r['dup_reads']}) | {r['plan_reads']} | {r['rules_loaded']} | {r['tool_errors']} | {' → '.join(r['outcomes'])} |")
    print("\nCommands per transcript (build/test/gate/git/sleep-poll) and top tools:")
    for r in rows:
        if r["commands"] or r["tools"]:
            print(f"- {(r['description'] or '(main) ' + r['file'][:8])[:40]}: {r['commands']} | {r['tools']}")


def cmd_runs(a):
    rx = re.compile(r"<command-name>/?([\w:-]+)</command-name>")
    args_rx = re.compile(r"<command-args>(.*?)</command-args>", re.S)
    written_rx = re.compile(r'plans(?:\\\\|/)+([^\\/"]+)(?:\\\\|/)+plan\.md')
    sessions = []
    for d in project_dirs(a.project, a.extra_dir):
        for p in glob.glob(os.path.join(d, "*.jsonl")):
            if ".orphaned-" in p:
                continue
            cmds, t0, t1, written = [], None, None, set()
            mentioned = collections.Counter()
            for line in open(p, encoding="utf-8", errors="replace"):
                if '"timestamp"' in line:
                    m = re.search(r'"timestamp":"([^"]+)"', line)
                    if m:
                        t0 = t0 or m.group(1); t1 = m.group(1)
                if "plan.md" in line:
                    found = written_rx.findall(line)
                    mentioned.update(found)
                    if '"name":"Write"' in line:
                        written.update(found)
                if "<command-name>" not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                txt = text_of(o.get("message", {}).get("content"))
                for m in rx.finditer(txt):
                    name = m.group(1).split(":")[-1]
                    if name in a.commands:
                        am = args_rx.search(txt)
                        cmds.append((name, (am.group(1).strip() if am else "")))
            if cmds and mentioned:
                # a re-invocation without arguments (resume) belongs to the plan the session works on
                top = mentioned.most_common(1)[0][0]
                cmds = [(n, arg or f"~/.claude/plans/{top}/plan.md" if n == "execute-plan" else arg) for n, arg in cmds]
            if cmds:
                n_sub = len(glob.glob(os.path.join(p[:-6], "subagents", "agent-*.jsonl")))
                sessions.append({"id": os.path.basename(p)[:-6], "dir": os.path.basename(d), "start": t0,
                                 "end": t1, "commands": cmds, "subagents": n_sub, "written": written})
    by_plan = collections.defaultdict(list)
    for s in sessions:
        for name, arg in s["commands"]:
            if name == "execute-plan":
                keys = [plan_key(arg)]
            elif s["written"]:
                keys = sorted(s["written"])
            else:
                keys = [f"({name}) {arg[:60]}"]
            for key in keys:
                by_plan[key].append((name, s))
    plans_dir = os.path.join(config_dir(), "plans")
    print(f"# Workflow sessions for {a.project}\n")
    print("A planning session is filed under the plan.md it wrote; one that wrote none, under its argument.\n")
    if not by_plan:
        print(f"No /write-plan or /execute-plan sessions found under {os.path.join(config_dir(), 'projects')} for this project.")
        print("Sessions in sibling checkouts: add --extra-dir <path>.")
        return
    items = sorted(by_plan.items(), key=lambda kv: max(s["start"] or "" for _, s in kv[1]), reverse=True)
    for key, lst in items[: a.limit]:
        plan_file = os.path.join(plans_dir, key, "plan.md") if key and not key.startswith("(") else None
        log = execution_log_state(plan_file) if plan_file else ""
        print(f"## {key} {log}")
        seen = set()
        for name, s in sorted(lst, key=lambda x: x[1]["start"] or ""):
            if (name, s["id"]) in seen:
                continue
            seen.add((name, s["id"]))
            print(f"- {name}: session `{s['id']}` in `{s['dir']}`, {(s['start'] or '')[:16]} → {(s['end'] or '')[:16]}, {s['subagents']} subagents")
        print()


def plan_key(arg):
    arg = arg.strip().strip('"').replace("\\", "/")
    m = re.search(r"plans/([^/]+)/plan\.md", arg)
    return m.group(1) if m else (arg or "(no argument)")


def execution_log_state(plan_file):
    if not plan_file or not os.path.isfile(plan_file):
        return "(plan file not found)"
    txt = open(plan_file, encoding="utf-8", errors="replace").read()
    i = txt.find("## Execution log")
    if i < 0:
        return "(no execution log)"
    body = txt[i + len("## Execution log"):].strip()
    lines = [l for l in body.splitlines() if l.strip() and not l.startswith("<")]
    return f"(execution log: {len(lines)} lines)"


def cmd_timeline(a):
    turns, tools, results, prompts = parse(a.file)
    err_ids = {r["id"] for r in results if r["error"]}
    res_by_id = {r["id"]: r for r in results}
    pr_by_turn = collections.defaultdict(list)
    for p in prompts:
        pr_by_turn[p["turn"]].append(p)
    grep = re.compile(a.grep, re.I) if a.grep else None
    prev_t = None
    for i, tr in enumerate(turns, 1):
        for p in pr_by_turn.get(i - 1, []):
            if (a.frm or 1) <= i <= (a.to or 10**9):
                if p.get("rule"):
                    print(f"      .. loaded {p['rule']}")
                elif p["text"].strip():
                    print(f"      >> user/orchestrator: {p['text'][:300].replace(chr(10), ' ')}")
        u = usage_split(tr["usage"])
        t = ts(tr["time"])
        gap = int((t - prev_t).total_seconds()) if (t and prev_t) else 0
        prev_t = t or prev_t
        if a.frm and i < a.frm or a.to and i > a.to:
            continue
        parts = []
        for x in tr["tools"]:
            inp = x["input"]
            arg = inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("prompt") or inp.get("description") or json.dumps(inp)[:80]
            if x["name"] == "Read" and (inp.get("offset") or inp.get("limit")):
                arg = f"{arg} [{inp.get('offset')}+{inp.get('limit')}]"
            r = res_by_id.get(x["id"])
            flag = " ERR" if x["id"] in err_ids else ""
            size = f" →{r['chars'] // 1000}k" if r and r["chars"] >= 1000 else ""
            parts.append(f"{x['name']}({str(arg)[:110].replace(chr(10), ' ')}){size}{flag}")
        line = "; ".join(parts) or "(text)"
        if grep and not grep.search(line):
            continue
        ctx = u["in"] + u["cr"] + u["write"]
        print(f"{i:4} {(tr['time'] or '')[11:19]} +{gap:>5}s ctx {ctx // 1000:>4}k w {u['write'] // 1000:>4}k out {u['out']:>6}  {line}")


def cmd_ttl(a):
    """Replay subagent turns as if their cache lived 1 h: turns after a 5–60 min gap read instead of rewrite."""
    mw = MODEL_WEIGHTS
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for ref in a.sessions:
        _, subs = resolve_session(ref, a.project, a.extra_dir)
        for p in subs:
            role = load_meta(p).get("agentType") or "?"
            turns, *_ = parse(p)
            prev_ctx = prev_t = None
            for tr in turns:
                u = usage_split(tr["usage"])
                w = model_weight(tr["model"], mw)
                cr, cc = u["cr"], u["write"]
                agg[role][0] += w * (1.25 * cc + 0.1 * cr)
                t = ts(tr["time"])
                gap = (t - prev_t).total_seconds() if (t and prev_t) else 0
                if prev_ctx and 300 < gap <= 3600 and cc > 0.5 * prev_ctx:
                    cr2 = min(prev_ctx, cr + cc)
                    agg[role][1] += w * (2 * (cr + cc - cr2) + 0.1 * cr2)
                    agg[role][2] += 1
                else:
                    agg[role][1] += w * (2 * cc + 0.1 * cr)
                prev_ctx, prev_t = u["in"] + cr + cc, (t or prev_t)
    print("Cache part only (reads + writes), M units. 'rescued' = turns a 1 h cache would have kept warm.\n")
    print("| role | 5 min (actual) | 1 h (replay) | delta | rescued turns |")
    print("|---|---:|---:|---:|---:|")
    for role, (act, sim, n) in sorted(agg.items()):
        print(f"| {role} | {act / 1e6:.2f} | {sim / 1e6:.2f} | {(sim - act) / 1e6:+.2f} | {n} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.getcwd(), help="project root (default: current directory)")
    ap.add_argument("--extra-dir", action="append", default=[],
                    help="another checkout whose transcripts belong to this project (sibling worktrees)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("runs"); r.add_argument("--limit", type=int, default=10)
    r.add_argument("--commands", default=",".join(COMMANDS))
    m = sp.add_parser("metrics"); m.add_argument("sessions", nargs="+"); m.add_argument("--json", action="store_true")
    m.add_argument("--weights", help='JSON, e.g. {"out": 5}'); m.add_argument("--model-weights", help='JSON, e.g. {"sonnet": 0.6}')
    t = sp.add_parser("timeline"); t.add_argument("file"); t.add_argument("--from", dest="frm", type=int)
    t.add_argument("--to", type=int); t.add_argument("--grep")
    x = sp.add_parser("ttl"); x.add_argument("sessions", nargs="+")
    a = ap.parse_args()
    if a.cmd == "runs":
        a.commands = tuple(c.strip() for c in a.commands.split(","))
        cmd_runs(a)
    elif a.cmd == "metrics":
        cmd_metrics(a)
    elif a.cmd == "timeline":
        cmd_timeline(a)
    else:
        cmd_ttl(a)


if __name__ == "__main__":
    main()
