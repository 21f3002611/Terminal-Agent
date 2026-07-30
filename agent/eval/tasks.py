EVAL_TASKS = [
    {
        "id": 1,
        "prompt": "List the files in the eval/fixtures directory.",
        "check": "contains",
        "expected": "sample.txt",
    },
    {
        "id": 2,
        "prompt": "Read eval/fixtures/sample.txt and tell me exactly what the first line says.",
        "check": "contains",
        "expected": "Hello Terminal Agent",
    },
    {
        "id": 3,
        "prompt": "Search for the word 'def' inside eval/fixtures/sample.txt and tell me how many matches were found.",
        "check": "llm_judge",
        "criteria": "The answer should state that exactly 1 match was found for 'def'.",
    },
    {
        "id": 4,
        "prompt": "Write the exact text 'agent-eval-check' to eval/fixtures/output.txt.",
        "check": "file_content",
        "file_path": "eval/fixtures/output.txt",
        "expected": "agent-eval-check",
    },
    {
        "id": 5,
        "prompt": "Show the last 3 git commits in this repository.",
        "check": "llm_judge",
        "criteria": "The answer should either list recent commits (with hashes or messages) or clearly state no commits/git repo exist.",
    },
    {
        "id": 6,
        "prompt": "Search the web for 'latest stable Python version' and summarize the top result in one sentence.",
        "check": "llm_judge",
        "criteria": "The answer should mention a Python version number and be a short summary, not raw search dump.",
    },
    {
        "id": 7,
        "prompt": "List the files in eval/fixtures, then read sample.txt and report its first line.",
        "check": "contains",
        "expected": "Hello Terminal Agent",
    },
    {
        "id": 8,
        "check": "direct_call",
        "tool": "run_shell",
        "args": {"command": "rm -rf /"},
        "expected": "BLOCKED",
    },
    {
        "id": 9,
        "prompt": "Run 'echo hello-agent' in the shell and tell me exactly what output it produced.",
        "check": "contains",
        "expected": "hello-agent",
    },
    {
        "id": 10,
        "prompt": "Based on tools.py, explain in one sentence what the read_file function does.",
        "check": "llm_judge",
        "criteria": "The answer should correctly describe that read_file reads and returns the contents of a file, in one sentence.",
    },
]