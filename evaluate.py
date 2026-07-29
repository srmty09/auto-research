import json
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.agent import Agent

TASKS = [
    {"id": "search_1", "goal": "What is the current population of Japan?", "category": "simple"},
    {"id": "search_2", "goal": "Who won the FIFA World Cup in 2022?", "category": "simple"},
    {"id": "code_1", "goal": "Calculate 15% of 8472", "category": "simple"},
    {"id": "code_2", "goal": "Compute the first 10 Fibonacci numbers", "category": "simple"},
    {"id": "multi_1", "goal": "Research the current CEO of NVIDIA and write their biography to a file", "category": "multi_step"},
    {"id": "multi_2", "goal": "Find the USD to EUR exchange rate and calculate how much 500 USD is in EUR", "category": "multi_step"},
    {"id": "multi_3", "goal": "Research Python 3.13 new features, summarize them, and save to a report", "category": "multi_step"},
]


def run_evaluation():
    agent = Agent()
    results = []

    print("=" * 60)
    print("AGENT EVALUATION")
    print("=" * 60)

    for task in TASKS:
        print(f"\n--- [{task['id']}] {task['goal'][:70]}... ---")
        start = time.time()
        try:
            result = agent.run(task["goal"])
            elapsed = time.time() - start
            tools_used = [s.get("tool") for s in result["log"] if s.get("tool")]
            entry = {
                "task_id": task["id"],
                "category": task["category"],
                "success": result["success"],
                "steps": result["steps"],
                "tools_used": tools_used,
                "time_seconds": round(elapsed, 2),
            }
            results.append(entry)
            icon = "PASS" if entry["success"] else "FAIL"
            print(f"  [{icon}] Steps:{entry['steps']} Tools:{tools_used} Time:{elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "task_id": task["id"],
                "category": task["category"],
                "success": False,
                "steps": -1,
                "tools_used": [],
                "time_seconds": round(elapsed, 2),
                "error": str(e),
            })
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = len(results)
    ok = sum(1 for r in results if r["success"])
    avg_steps = sum(r["steps"] for r in results if r["steps"] > 0) / max(
        sum(1 for r in results if r["steps"] > 0), 1
    )
    avg_time = sum(r["time_seconds"] for r in results) / total
    print(f"Total tasks:    {total}")
    print(f"Success rate:   {ok}/{total} ({ok / total * 100:.1f}%)")
    print(f"Avg steps:      {avg_steps:.1f}")
    print(f"Avg time:       {avg_time:.1f}s")

    workspace = Path(os.path.dirname(__file__)) / "workspace"
    workspace.mkdir(exist_ok=True)
    out = workspace / "evaluation_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {out}")

    return results


if __name__ == "__main__":
    run_evaluation()
