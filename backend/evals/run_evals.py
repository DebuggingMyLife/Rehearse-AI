"""Evaluator test set: run the scoring pipeline on fixed sample answers against the configured
local model and report score consistency, so models and settings can be compared.

    cd backend
    python -m evals.run_evals                  # 3 runs per sample, scoring only
    python -m evals.run_evals --runs 5 --feedback
    python -m evals.run_evals --model llama3.1:8b

Each sample has an expected score band (strong 4-5, weak 1-2, off-topic 1-2, empty 1). The
report shows every run's score, mean, spread, how often the score landed in the band, how
often Python had to correct an inconsistent model score, and call timings. A JSON copy is
saved to evals/results/ for side-by-side comparison of models.
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.services.evaluation import EvaluationContext, score_answer, write_feedback
from app.services.llm import LLMUnavailable, OllamaClient, check_ollama
from app.services.pipeline import MIN_WORDS

HERE = Path(__file__).parent


def word_count(text: str) -> int:
    return len([w for w in text.split() if any(c.isalnum() for c in w)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", help="override LLM_MODEL for this run")
    ap.add_argument("--feedback", action="store_true", help="also run call 2 (feedback) and time it")
    ap.add_argument("--only", help="comma-separated sample names")
    args = ap.parse_args()

    settings = get_settings()
    if args.model:
        settings = settings.model_copy(update={"llm_model": args.model})
    status = check_ollama(settings)
    if not status.ok:
        print(f"Ollama not ready: {status.error} Fix: {status.fix}")
        return 2
    llm = OllamaClient(settings)

    data = json.loads((HERE / "samples.json").read_text(encoding="utf-8"))
    samples = data["samples"]
    if args.only:
        wanted = set(args.only.split(","))
        samples = [s for s in samples if s["name"] in wanted]

    print(f"Model {settings.llm_model} · num_ctx {settings.llm_num_ctx} · temperature {settings.llm_temperature}"
          f" · {args.runs} run(s) per sample\n")
    results = []
    for s in samples:
        ctx = EvaluationContext(
            question=s["question"], question_type=s["type"], difficulty=s["difficulty"], rubric=s["rubric"],
            cv_text=data["cv_text"], job_description=data["job_description"], transcript=s["transcript"],
            cv_evidence=[], behavioural=s["type"] == "behavioural",
        )
        gated = word_count(s["transcript"]) < MIN_WORDS
        runs = []
        for i in range(args.runs):
            run: dict = {}
            t = time.perf_counter()
            try:
                scoring, _ = score_answer(llm, ctx, f"eval:{s['name']}:{i}")
                run.update(score=scoring["score"], model_score=scoring.get("model_score", scoring["score"]),
                           covered=sum(c["covered"] for c in scoring["rubric_coverage"]),
                           unverified_claims=sum(bool(c.get("unverified_claim")) for c in scoring["rubric_coverage"]))
            except LLMUnavailable as exc:
                run["error"] = str(exc)
            run["score_ms"] = int((time.perf_counter() - t) * 1000)
            if args.feedback and "score" in run:
                t = time.perf_counter()
                try:
                    fb, _ = write_feedback(llm, ctx, scoring, None, f"eval:{s['name']}:{i}")
                    run["feedback_ok"] = True
                    run["example_sentences_removed"] = fb.get("example_answer_sentences_removed", 0)
                except LLMUnavailable as exc:
                    run["feedback_ok"] = False
                    run["feedback_error"] = str(exc)
                run["feedback_ms"] = int((time.perf_counter() - t) * 1000)
            runs.append(run)

        scores = [r["score"] for r in runs if "score" in r]
        lo, hi = s["expected"]
        result = {
            "name": s["name"], "kind": s["kind"], "expected": [lo, hi],
            "app_gate": "re-record prompt (not scored)" if gated else "scored",
            "scores": scores,
            "model_scores": [r["model_score"] for r in runs if "model_score" in r],
            "mean": round(statistics.mean(scores), 2) if scores else None,
            "stdev": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0,
            "range": (max(scores) - min(scores)) if scores else None,
            "in_band": sum(lo <= x <= hi for x in scores),
            "corrected": sum(r.get("model_score") != r.get("score") for r in runs if "score" in r),
            "failures": sum("error" in r for r in runs),
            "avg_score_ms": int(statistics.mean(r["score_ms"] for r in runs)),
            "runs": runs,
        }
        if args.feedback:
            fb_ms = [r["feedback_ms"] for r in runs if "feedback_ms" in r]
            result["avg_feedback_ms"] = int(statistics.mean(fb_ms)) if fb_ms else None
            result["feedback_failures"] = sum(r.get("feedback_ok") is False for r in runs)
        results.append(result)
        flag = "OK " if result["in_band"] == len(runs) and not result["failures"] else "!! "
        print(f"{flag}{s['name']:<24} expected {lo}-{hi}  scores {scores}  "
              f"(model said {result['model_scores']})  stdev {result['stdev']}  "
              f"in band {result['in_band']}/{len(runs)}  {result['avg_score_ms']} ms"
              + (f"  feedback {result['avg_feedback_ms']} ms, {result['feedback_failures']} failed"
                 if args.feedback else "")
              + ("  [app gate: re-record]" if gated else ""))

    total = sum(len(r["runs"]) for r in results)
    in_band = sum(r["in_band"] for r in results)
    consistent = sum(1 for r in results if r["range"] == 0)
    summary = {
        "model": settings.llm_model, "num_ctx": settings.llm_num_ctx, "temperature": settings.llm_temperature,
        "runs_per_sample": args.runs, "timestamp": datetime.now().isoformat(timespec="seconds"),
        "in_band_rate": round(in_band / total, 3) if total else None,
        "samples_fully_consistent": f"{consistent}/{len(results)}",
        "mean_stdev": round(statistics.mean(r["stdev"] for r in results), 3) if results else None,
        "corrections": sum(r["corrected"] for r in results),
        "failures": sum(r["failures"] for r in results),
        "feedback_failures": sum(r.get("feedback_failures", 0) for r in results) if args.feedback else None,
    }
    print(f"\nIn expected band: {in_band}/{total} ({summary['in_band_rate']:.0%})  ·  "
          f"identical score every run: {summary['samples_fully_consistent']} samples  ·  "
          f"mean stdev {summary['mean_stdev']}  ·  score corrections {summary['corrections']}  ·  "
          f"failures {summary['failures']}"
          + (f"  ·  feedback failures {summary['feedback_failures']}" if args.feedback else ""))

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{settings.llm_model.replace(':', '_').replace('/', '_')}_{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(f"Saved {out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
