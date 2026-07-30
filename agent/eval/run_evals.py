import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # add agent/ to path

from tools import run_agent, TOOL_FUNCTIONS  # noqa: E402
from eval.tasks import EVAL_TASKS  # noqa: E402
from eval.judge import llm_judge  # noqa: E402


def check_contains(answer: str, expected: str) -> bool:
    return expected in answer


def check_contains_ci(answer: str, expected: str) -> bool:
    return expected.lower() in answer.lower()


def check_file_content(task: dict) -> bool:
    """Bypasses the LLM's own report entirely — reads the actual file on disk.
    This is the strongest kind of check: it verifies the tool really did the
    thing, not just that the model claimed it did."""
    path = task["file_path"]
    try:
        with open(path, "r") as f:
            return f.read().strip() == task["expected"].strip()
    except Exception:
        return False


def run_evals():
    results = []
    for task in EVAL_TASKS:
        if task["check"] == "direct_call":
            print(f"\n=== Task {task['id']}: direct call {task['tool']}({task['args']}) ===")
            result = TOOL_FUNCTIONS[task["tool"]](**task["args"])
            passed = task["expected"] in result
            reason = f"expected substring: '{task['expected']}', got: '{result}'"
            results.append({"id": task["id"], "prompt": f"direct_call:{task['tool']}", "passed": passed, "reason": reason})
            print(f"Result: {'PASS' if passed else 'FAIL'} ({reason})")
            continue

        print(f"\n=== Task {task['id']}: {task['prompt']} ===")
        answer = run_agent(task["prompt"]) or ""

        if task["check"] == "contains":
            passed = check_contains(answer, task["expected"])
            reason = f"expected substring: '{task['expected']}'"
        elif task["check"] == "contains_ci":
            passed = check_contains_ci(answer, task["expected"])
            reason = f"expected (case-insensitive): '{task['expected']}'"
        elif task["check"] == "file_content":
            passed = check_file_content(task)
            reason = f"expected file content: '{task['expected']}'"
        elif task["check"] == "llm_judge":
            passed, reason = llm_judge(answer, task["criteria"])
        else:
            passed, reason = False, "unknown check type"

        results.append({"id": task["id"], "prompt": task["prompt"], "passed": passed, "reason": reason})
        print(f"Result: {'PASS' if passed else 'FAIL'} ({reason})")

    passed_count = sum(r["passed"] for r in results)
    total = len(results)
    print(f"\n=== SUMMARY: {passed_count}/{total} passed ({passed_count/total:.0%}) ===")

    with open("eval/results.json", "w") as f:
        json.dump({"pass_rate": passed_count / total, "results": results}, f, indent=2)

    return results


if __name__ == "__main__":
    run_evals()