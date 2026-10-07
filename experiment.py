"""Experiment Mode for JARVIS.

QUESTION → HYPOTHESIS → DESIGN → EXECUTE → ANALYZE → CONCLUDE

Design: 2 LLM calls max (+1 optional follow-up). Everything else is
deterministic Python. Artifacts saved to experiments/<id>/.
Persistence: SQLite (experiments.db).
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "experiments.db"
EXP_DIR = ROOT / "experiments"
EXP_DIR.mkdir(exist_ok=True)

BLOCKED = [
    "os.system", "os.popen", "subprocess.Popen", "shutil.rmtree",
    "socket.", "urllib.request", "requests.post", "__import__('os').system",
]


# ═══════════════════════════════════════════════════════════════
#  PERSISTENCE
# ═══════════════════════════════════════════════════════════════

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            ts REAL NOT NULL,
            question TEXT NOT NULL,
            spec_json TEXT,
            results_json TEXT,
            analysis_json TEXT,
            conclusion TEXT,
            confidence TEXT,
            status TEXT DEFAULT 'created'
        );
        CREATE INDEX IF NOT EXISTS idx_ts ON experiments(ts);
        """)


def _save(exp_id, **fields):
    _init_db()
    with _conn() as c:
        row = c.execute("SELECT id FROM experiments WHERE id = ?", (exp_id,)).fetchone()
        if not row:
            c.execute(
                "INSERT INTO experiments (id, ts, question) VALUES (?, ?, ?)",
                (exp_id, time.time(), fields.get("question", "")),
            )
        for k, v in fields.items():
            if k == "question" or v is None:
                continue
            c.execute(f"UPDATE experiments SET {k} = ? WHERE id = ?", (v, exp_id))


def list_experiments(limit=20):
    _init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT id, ts, question, conclusion, confidence, status "
            "FROM experiments ORDER BY ts DESC LIMIT ?", (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_experiment(exp_id):
    _init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════
#  PROMPTS
# ═══════════════════════════════════════════════════════════════

PLAN_PROMPT = """You are an experimental design engine. Given a user's research question, produce a STRICT JSON experiment specification. No prose. No markdown. Only valid JSON.

Keys required:
{
  "hypothesis": "one sentence, falsifiable",
  "null_hypothesis": "one sentence negating hypothesis",
  "independent_variables": ["what we change"],
  "dependent_variables": ["what we measure"],
  "controls": ["what stays constant"],
  "trials": [list of values, e.g. [0.2, 0.4, 0.6, 0.8, 1.0]],
  "baseline": "what baseline is, or 'none' with reason",
  "metric": "primary metric e.g. RMSE, accuracy",
  "expected_result": "one sentence prediction",
  "code": "complete self-contained Python script"
}

CRITICAL RULES FOR "code":
- Complete standalone Python script.
- MUST print a single JSON object to stdout at the end:
  {"trials":[{"trial":1,"independent":0.2,"metric_value":41.2}],"baseline":{"metric_value":45.0,"description":"..."},"metric":"RMSE","notes":"..."}
- Forbidden: os.system, subprocess, socket, requests, shutil.rmtree.
- Allowed imports: numpy, pandas, sklearn, scipy, matplotlib, json, math, statistics, random.
- Set random seeds (numpy, random) for reproducibility.
- Save any plots as .png in the current directory.
- If no dataset provided, GENERATE synthetic data with a fixed seed.
- Under 80 lines. Use single quotes for strings inside code (simpler JSON escaping).
- matplotlib: use matplotlib.use('Agg') before importing pyplot.

Return ONLY the JSON object."""


ANALYZE_PROMPT = """You are a results interpreter. Given an experiment spec and compact results, produce STRICT JSON. No prose. Only valid JSON.

Keys required:
{
  "observed": "plain restatement of the numbers, no interpretation",
  "interpretation": "what it means given the hypothesis",
  "hypothesis_supported": true | false | "inconclusive",
  "surprising": "unexpected finding, or null",
  "followup_needed": true | false,
  "followup_question": "if needed, one sentence; else null",
  "conclusion": "one paragraph final answer",
  "confidence": "low" | "medium" | "high",
  "limitations": ["list"]
}

Rules:
- "observed" = pure fact restatement.
- "interpretation" = clearly separate from observed.
- "followup_needed" only if genuinely inconclusive AND resolvable by ONE targeted experiment.
- Confidence from effect size and consistency, not vibes.

Return ONLY the JSON object."""


# ═══════════════════════════════════════════════════════════════
#  LLM BRIDGE (1 call, JSON only)
# ═══════════════════════════════════════════════════════════════

def _llm_json(system_prompt, user_content, brain):
    """One LLM call. Returns parsed JSON or raises."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    models_list = getattr(brain, "MODELS", [])
    if not models_list:
        raise RuntimeError("No MODELS found in brain.py")

    last_err = None
    for client, model in models_list:
        for use_json_mode in (True, False):
            try:
                kwargs = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2000,
                    "temperature": 0.2,
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                text = resp.choices[0].message.content or ""
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_err = e
                continue
            except Exception as e:
                err_str = str(e).lower()
                if use_json_mode and (
                    "response_format" in err_str
                    or "json_object" in err_str
                    or "not supported" in err_str
                ):
                    # retry this same model without JSON mode
                    continue
                last_err = e
                break  # next model
    raise RuntimeError(f"LLM JSON call failed: {last_err}")


# ═══════════════════════════════════════════════════════════════
#  SANDBOX
# ═══════════════════════════════════════════════════════════════

def _check_safe(code):
    for kw in BLOCKED:
        if kw in code:
            return f"Blocked: '{kw}' is not allowed"
    return None


def _run_code(code, workdir, timeout=180):
    script = workdir / "experiment.py"
    script.write_text(code, encoding="utf-8")
    try:
        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(workdir),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"Timed out after {timeout}s", -1
    except Exception as e:
        return "", f"Execution error: {e}", -1


def _extract_json_from_stdout(stdout):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        pass
    matches = re.findall(r"\{[\s\S]*\}", stdout)
    for m in reversed(matches):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_experiment(question, brain, on_progress=None):
    def _p(msg):
        if on_progress:
            on_progress(msg)
        else:
            print(msg)

    exp_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"
    workdir = EXP_DIR / exp_id
    workdir.mkdir(exist_ok=True)
    plots_dir = workdir / "plots"
    plots_dir.mkdir(exist_ok=True)

    _init_db()
    _save(exp_id, question=question, status="planning")
    _p(f"🧪 Experiment Mode — {exp_id}")
    _p(f"Question → {question}")

    # ── LLM CALL 1: PLAN ──
    _p("Hypothesis → generating")
    try:
        spec = _llm_json(PLAN_PROMPT, question, brain)
    except Exception as e:
        _save(exp_id, status="failed_planning")
        return {"ok": False, "error": f"Planning failed: {e}", "experiment_id": exp_id}

    if "code" not in spec or not isinstance(spec.get("code"), str):
        _save(exp_id, status="failed_planning")
        return {"ok": False, "error": "Planning returned no code", "experiment_id": exp_id}

    (workdir / "experiment.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    _save(exp_id, spec_json=json.dumps(spec), status="planned")
    _p(f"Hypothesis → {spec.get('hypothesis', '?')}")

    # ── EXECUTE ──
    code = spec["code"]
    err = _check_safe(code)
    if err:
        _save(exp_id, status="failed_safety")
        return {"ok": False, "error": err, "experiment_id": exp_id}

    _p("Execution → running")
    t0 = time.time()
    stdout, stderr, rc = _run_code(code, workdir, timeout=180)
    elapsed = time.time() - t0

    # Move plots
    for png in workdir.glob("*.png"):
        try:
            shutil.move(str(png), str(plots_dir / png.name))
        except Exception:
            pass

    if rc != 0:
        _p(f"Execution → failed, retrying with feedback")
        corrected = _try_correction(spec, stderr, brain)
        if corrected:
            (workdir / "experiment.json").write_text(
                json.dumps({**spec, "code": corrected}, indent=2), encoding="utf-8",
            )
            stdout, stderr, rc = _run_code(corrected, workdir, timeout=180)

    if rc != 0:
        _save(exp_id, status="failed_execution")
        return {"ok": False, "error": f"Execution failed: {stderr[:500]}",
                "experiment_id": exp_id}

    results = _extract_json_from_stdout(stdout)
    if not results:
        _save(exp_id, status="failed_no_results")
        return {"ok": False, "error": "No parseable results JSON",
                "experiment_id": exp_id, "raw_stdout": stdout[:500]}

    results["_meta"] = {
        "seed": "see experiment.py",
        "elapsed_seconds": round(elapsed, 2),
        "python": sys.version.split()[0],
        "exp_id": exp_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    (workdir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    _save(exp_id, results_json=json.dumps(results), status="executed")
    _p("Execution → complete")

    # ── LLM CALL 2: ANALYZE ──
    _p("Analysis → interpreting")
    analysis_input = {
        "question": question,
        "hypothesis": spec.get("hypothesis"),
        "null_hypothesis": spec.get("null_hypothesis"),
        "metric": spec.get("metric"),
        "baseline": spec.get("baseline"),
        "results": results,
    }
    try:
        analysis = _llm_json(ANALYZE_PROMPT, json.dumps(analysis_input), brain)
    except Exception as e:
        _save(exp_id, status="failed_analysis")
        return {"ok": False, "error": f"Analysis failed: {e}", "experiment_id": exp_id}

    _save(exp_id,
          analysis_json=json.dumps(analysis),
          conclusion=analysis.get("conclusion", ""),
          confidence=analysis.get("confidence", "unknown"),
          status="complete")
    _p("Analysis → complete")

    # ── OPTIONAL FOLLOW-UP (max 1) ──
    followup = None
    if analysis.get("followup_needed") and analysis.get("followup_question"):
        _p(f"Follow-up → {analysis['followup_question']}")
        followup = _run_followup(exp_id, spec, analysis, brain, on_progress)

    report = _build_report(exp_id, question, spec, results, analysis, followup)
    (workdir / "report.md").write_text(report, encoding="utf-8")

    return {
        "ok": True,
        "experiment_id": exp_id,
        "spec": spec,
        "results": results,
        "analysis": analysis,
        "followup": followup,
        "report": report,
        "artifacts_dir": str(workdir),
    }


def _try_correction(spec, stderr, brain):
    if not stderr:
        return None
    prompt = (
        "The following Python script failed. Return ONLY JSON: "
        '{"code": "..."} with the corrected script. Keep under 80 lines.\n\n'
        f"CODE:\n{spec['code']}\n\nERROR:\n{stderr[:1500]}"
    )
    try:
        out = _llm_json("You are a Python debugger. Return only JSON.", prompt, brain)
        return out.get("code")
    except Exception:
        return None


def _run_followup(parent_id, parent_spec, parent_analysis, brain, on_progress=None):
    def _p(msg):
        if on_progress:
            on_progress(msg)

    follow_id = f"{parent_id}-F"
    workdir = EXP_DIR / follow_id
    workdir.mkdir(exist_ok=True)

    try:
        spec = _llm_json(
            PLAN_PROMPT,
            f"Follow-up experiment.\n"
            f"Previous hypothesis: {parent_spec.get('hypothesis')}\n"
            f"Previous observed: {parent_analysis.get('observed')}\n"
            f"Unexpected: {parent_analysis.get('surprising')}\n"
            f"Follow-up question: {parent_analysis.get('followup_question')}",
            brain,
        )
    except Exception as e:
        return {"ok": False, "error": f"Follow-up planning failed: {e}"}

    (workdir / "experiment.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    if _check_safe(spec.get("code", "")):
        return {"ok": False, "error": "Follow-up code blocked"}

    stdout, stderr, rc = _run_code(spec["code"], workdir, timeout=180)
    if rc != 0:
        return {"ok": False, "error": f"Follow-up execution failed: {stderr[:300]}"}

    results = _extract_json_from_stdout(stdout)
    if not results:
        return {"ok": False, "error": "No parseable follow-up results"}

    (workdir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    try:
        analysis = _llm_json(
            ANALYZE_PROMPT,
            json.dumps({
                "question": parent_analysis.get("followup_question"),
                "hypothesis": spec.get("hypothesis"),
                "metric": spec.get("metric"),
                "baseline": spec.get("baseline"),
                "results": results,
                "context": "follow-up experiment",
            }),
            brain,
        )
    except Exception as e:
        return {"ok": False, "error": f"Follow-up analysis failed: {e}"}

    return {"ok": True, "experiment_id": follow_id, "spec": spec,
            "results": results, "analysis": analysis}


def _build_report(exp_id, question, spec, results, analysis, followup):
    lines = [
        f"# Experiment: {exp_id}", "",
        "## Question", question, "",
        "## Hypothesis", spec.get("hypothesis", "—"), "",
        "## Null hypothesis", spec.get("null_hypothesis", "—"), "",
        "## Method",
        f"- **Independent variable:** {', '.join(spec.get('independent_variables', []))}",
        f"- **Dependent variable:** {', '.join(spec.get('dependent_variables', []))}",
        f"- **Controls:** {', '.join(spec.get('controls', []))}",
        f"- **Trials:** {spec.get('trials', [])}",
        f"- **Metric:** {spec.get('metric', '—')}",
        f"- **Baseline:** {spec.get('baseline', '—')}", "",
        "## Results (OBSERVED)", analysis.get("observed", "—"), "",
        "## Interpretation", analysis.get("interpretation", "—"), "",
        f"**Hypothesis supported:** {analysis.get('hypothesis_supported')}",
        f"**Confidence:** {analysis.get('confidence')}", "",
    ]
    if analysis.get("surprising"):
        lines += ["## Surprising", analysis["surprising"], ""]
    lines += ["## Conclusion", analysis.get("conclusion", "—"), "", "## Limitations"]
    for lim in analysis.get("limitations", []) or ["—"]:
        lines.append(f"- {lim}")
    lines += ["", "## Reproducibility"]
    for k, v in (results.get("_meta") or {}).items():
        lines.append(f"- **{k}:** {v}")
    if followup and followup.get("ok"):
        lines += [
            "", "## Follow-up Experiment",
            f"**Question:** {analysis.get('followup_question')}",
            f"**Hypothesis:** {followup['spec'].get('hypothesis')}",
            f"**Conclusion:** {followup['analysis'].get('conclusion')}",
        ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  TOOL ENTRY POINTS
# ═══════════════════════════════════════════════════════════════

def experiment_run(question):
    import brain
    result = run_experiment(question, brain, on_progress=print)
    if not result.get("ok"):
        return f"🧪 Experiment failed: {result.get('error','unknown')}"
    a = result["analysis"]
    lines = [
        f"🧪 Experiment {result['experiment_id']}", "",
        f"**Hypothesis:** {result['spec'].get('hypothesis')}", "",
        f"**Observed:** {a.get('observed','—')}", "",
        f"**Interpretation:** {a.get('interpretation','—')}", "",
        f"**Conclusion:** {a.get('conclusion','—')}", "",
        f"**Confidence:** {a.get('confidence','—')}",
    ]
    if a.get("followup_needed"):
        lines.append(f"**Follow-up ran:** {a.get('followup_question')}")
    lines.append(f"**Artifacts:** {result['artifacts_dir']}")
    return "\n".join(lines)


def experiment_list():
    exps = list_experiments(20)
    if not exps:
        return "No experiments yet."
    lines = ["**Past experiments:**", ""]
    for e in exps:
        ts = datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"- `{e['id']}` ({ts}) — {e['question'][:70]} [{e['status']}]")
    return "\n".join(lines)


def experiment_show(exp_id):
    e = get_experiment(exp_id)
    if not e:
        return f"No experiment with ID {exp_id}."
    return (f"**{e['id']}**\nQuestion: {e['question']}\n"
            f"Status: {e['status']}\nConfidence: {e['confidence'] or '—'}\n"
            f"Conclusion: {e['conclusion'] or '—'}")