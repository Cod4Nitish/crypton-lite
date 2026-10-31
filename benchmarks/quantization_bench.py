"""Reproducible local quantization benchmark against Ollama. No downloads, no network beyond localhost.

    .venv/Scripts/python benchmarks/quantization_bench.py [--models a b] [--trials 3]

Models are grouped by (family, parameter_size). A quantization COMPARISON is only claimed when a group has
two or more installed variants; otherwise the report says what is missing and runs a baseline per model.
Every number comes from Ollama's own response fields, perf_counter, or nvidia-smi. Nothing is estimated.
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import httpx

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from backend import tools  # noqa: E402  (same tool schemas the real agent sends)
from backend.agent import _content_tool_call  # noqa: E402

URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 128}
TOOLS = [tools.REGISTRY[n].schema() for n in ("create_task", "list_tasks", "complete_task")]

# Identical for every model. `check` is a deterministic pass/fail, no LLM judge.
TESTS = [
    {"id": "arithmetic", "messages": [{"role": "user", "content": "What is 17 * 23? Reply with only the number."}],
     "check": lambda m, calls: "391" in (m.get("content") or "")},
    {"id": "extraction", "messages": [{"role": "user", "content": "Text: 'Submissions close at 14:00 on Saturday.' Reply with only the closing time as HH:MM."}],
     "check": lambda m, calls: "14:00" in (m.get("content") or "")},
    {"id": "tool-selection", "tools": TOOLS,
     "messages": [{"role": "system", "content": "You are a task agent. Use the provided tools."},
                  {"role": "user", "content": "Remind me to call mom tomorrow, it is high priority."}],
     "check": lambda m, calls: bool(calls) and calls[0]["function"]["name"] == "create_task"
     and str((calls[0]["function"].get("arguments") or {}).get("priority", "")).lower() == "high"},
]


def get(path):
    return httpx.get(f"{URL}{path}", timeout=10).json()


def post(path, body, timeout=300):
    return httpx.post(f"{URL}{path}", json=body, timeout=timeout).json()


def gpu_used_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.split()
        return int(out[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


class VramSampler:
    """Polls whole-GPU memory.used. Includes other processes, so peak is reported as a delta vs. baseline."""

    def __init__(self):
        self.base, self.peak, self._stop = gpu_used_mib(), None, threading.Event()

    def __enter__(self):
        if self.base is not None:
            self.peak = self.base
            threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        while not self._stop.is_set():
            v = gpu_used_mib()
            if v is not None:
                self.peak = max(self.peak, v)
            time.sleep(0.15)

    def __exit__(self, *a):
        self._stop.set()

    @property
    def delta(self):
        return None if self.base is None else self.peak - self.base


def unload(model):
    post("/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
    time.sleep(1)


def call(model, test):
    body = {"model": model, "messages": test["messages"], "stream": False, "think": False, "keep_alive": "5m", "options": OPTIONS}
    if test.get("tools"):
        body["tools"] = test["tools"]
    t0 = time.perf_counter()
    d = post("/api/chat", body)
    wall = time.perf_counter() - t0
    if "message" not in d:
        return {"test": test["id"], "error": d.get("error", "no message")}
    msg = d["message"]
    calls = msg.get("tool_calls") or _content_tool_call(msg.get("content", ""))
    sec = lambda ns: ns / 1e9 if ns else None  # noqa: E731
    pe, ge = sec(d.get("prompt_eval_duration")), sec(d.get("eval_duration"))
    return {
        "test": test["id"], "passed": bool(test["check"](msg, calls)),
        "wall_s": round(wall, 3), "total_s": round(sec(d.get("total_duration")) or 0, 3),
        "load_s": round(sec(d.get("load_duration")) or 0, 3),
        "prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count"),
        "prompt_tok_s": round(d["prompt_eval_count"] / pe, 1) if pe and d.get("prompt_eval_count") else None,
        "gen_tok_s": round(d["eval_count"] / ge, 1) if ge and d.get("eval_count") else None,
        "output": (msg.get("content") or json.dumps(calls))[:160],
    }


def bench_model(model, info, trials):
    print(f"\n== {model}  ({info['details'].get('quantization_level')})", flush=True)
    unload(model)
    runs, cold = [], None
    with VramSampler() as vs:
        for trial in range(trials):
            for test in TESTS:
                r = call(model, test)
                r["trial"] = trial
                if cold is None and "error" not in r:
                    cold = r["load_s"]
                runs.append(r)
                print(f"  trial {trial} {test['id']:15s} " + (r.get("error") or f"{'PASS' if r['passed'] else 'FAIL'} {r['gen_tok_s']} tok/s {r['wall_s']}s"), flush=True)
    ps = next((m for m in get("/api/ps").get("models", []) if m["name"] == model), {})
    ok = [r for r in runs if "error" not in r]

    def med(k):
        vals = [r[k] for r in ok if r.get(k) is not None]
        return round(statistics.median(vals), 2) if vals else None

    out = {
        "model": model, "family": info["details"].get("family"), "parameter_size": info["details"].get("parameter_size"),
        "quantization": info["details"].get("quantization_level"), "file_size_gib": round(info["size"] / 2**30, 2),
        "context_length_max": next((v for k, v in info["model_info"].items() if k.endswith(".context_length")), None),
        "num_ctx_used": OPTIONS["num_ctx"], "trials": trials, "calls": len(runs), "errors": len(runs) - len(ok),
        "cold_load_s": cold, "prompt_tok_s_median": med("prompt_tok_s"), "gen_tok_s_median": med("gen_tok_s"),
        "wall_s_median": med("wall_s"), "wall_s_max": max((r["wall_s"] for r in ok), default=None),
        "ollama_resident_mib": round(ps["size"] / 2**20) if ps else None,
        "ollama_vram_mib": round(ps["size_vram"] / 2**20) if ps else None,
        "gpu_peak_delta_mib": vs.delta,
        "quality": {"passed": sum(r["passed"] for r in ok), "total": len(ok),
                    "by_test": {t["id"]: f"{sum(r['passed'] for r in ok if r['test'] == t['id'])}/{sum(1 for r in ok if r['test'] == t['id'])}" for t in TESTS}},
        "raw": runs,
    }
    unload(model)
    return out


def machine():
    gpu = "none detected"
    if gpu_used_mib() is not None:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True).stdout.strip()
    return {"os": platform.platform(), "cpu": platform.processor(), "gpu": gpu, "ollama": get("/api/version").get("version")}


def write_md(res, path):
    L = ["# Quantization benchmark results", "",
         f"Generated {res['generated_at']} by `benchmarks/quantization_bench.py`. All values are measured on this machine; nothing is estimated.", "",
         f"- Machine: {res['machine']['cpu']} | GPU: {res['machine']['gpu']} | Ollama {res['machine']['ollama']}",
         f"- Settings: `{json.dumps(OPTIONS)}`, `think=false`, {res['trials']} trials x {len(TESTS)} identical tests per model", "",
         "## Comparison status", ""]
    for g in res["groups"]:
        L.append(f"- **{g['key']}**: " + (f"{len(g['models'])} variants installed ({', '.join(g['models'])}): comparable." if len(g["models"]) > 1
                 else f"only `{g['models'][0]}` installed. **No same-model quantization comparison is possible.** Missing: another quantization of the same model (for example a Q8_0 build). Nothing was downloaded."))
    L += ["", "## Per-model results (baseline, not a quantization comparison unless stated above)", "",
          "| Model | Quant | File GiB | Cold load s | Prompt tok/s | Gen tok/s | Median latency s | Max latency s | Ollama VRAM MiB | Ollama resident MiB | GPU peak delta MiB | Quality |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in res["models"]:
        L.append(f"| {m['model']} | {m['quantization']} | {m['file_size_gib']} | {m['cold_load_s']} | {m['prompt_tok_s_median']} | {m['gen_tok_s_median']} | {m['wall_s_median']} | {m['wall_s_max']} | {m['ollama_vram_mib']} | {m['ollama_resident_mib']} | {m['gpu_peak_delta_mib']} | {m['quality']['passed']}/{m['quality']['total']} |")
    L += ["", "Quality by test: " + "; ".join(f"{m['model']}: {m['quality']['by_test']}" for m in res["models"]), "",
          "## Caveats", "",
          "- Different models (e.g. a 4B vs a 7B) differ in more than quantization; their rows must not be read as a quantization effect.",
          "- `GPU peak delta` is whole-GPU memory growth sampled every 150 ms and can include other processes. `Ollama VRAM` comes from `/api/ps` after the run.",
          f"- Quality is {len(TESTS)} tiny deterministic checks; it detects breakage, not subtle quality loss. Small sample, no statistical claims.",
          "- Re-run to reproduce; numbers vary with thermal state and background GPU load."]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(ROOT, "benchmarks", "quantization_results.json"))
    ap.add_argument("--md", default=os.path.join(ROOT, "docs", "QUANTIZATION_RESULTS.md"))
    a = ap.parse_args()
    infos = {}
    for t in get("/api/tags")["models"]:
        s = post("/api/show", {"model": t["name"]}, timeout=30)
        if "embedding" in (s.get("capabilities") or []):
            continue
        s["size"] = t["size"]
        infos[t["name"]] = s
    names = a.models or sorted(infos)
    groups = {}
    for n in infos:
        d = infos[n]["details"]
        groups.setdefault(f"{d.get('family')} {d.get('parameter_size')}", []).append(n)
    results = [bench_model(n, infos[n], a.trials) for n in names if n in infos]
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "machine": machine(), "options": OPTIONS,
           "trials": a.trials, "groups": [{"key": k, "models": v, "comparable": len(v) > 1} for k, v in groups.items()], "models": results}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    write_md(res, a.md)
    print(f"\nwrote {a.out}\nwrote {a.md}")


if __name__ == "__main__":
    main()
