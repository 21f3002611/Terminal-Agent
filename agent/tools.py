import os
import json
import subprocess
from groq import Groq
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])
tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

MODEL = "llama-3.3-70b-versatile"
MAX_STEPS = 10  # hard stop so a confused agent can't loop forever

# Commands/patterns that get blocked outright, regardless of what the LLM asks for.
# This is a blocklist, not a sandbox — it stops obvious disasters, not a determined attacker.
DANGEROUS_PATTERNS = [
    "rm -rf", "sudo", "mkfs", "dd if=", "shutdown", "reboot",
    "> /dev/", ":(){ :|:& };:",  # fork bomb
    "curl | sh", "wget | sh", "| sh", "| bash",
]

# ---- Tool implementations: what actually runs on your machine ----


def read_file(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()[:4000]  # cap size — don't blow the context window
    except Exception as e:
        return f"ERROR: {e}"


def write_file(path: str, content: str) -> str:
    """First tool that changes the filesystem (read_file only observes) —
    treat write access more carefully than read access."""
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"ERROR: {e}"


def list_dir(path: str = ".") -> str:
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:
        return f"ERROR: {e}"


def grep(pattern: str, path: str = ".") -> str:
    """Wraps the real `grep` binary instead of reimplementing search in Python —
    reuse battle-tested tools rather than rebuilding them."""
    try:
        result = subprocess.run(
            ["grep", "-rn", pattern, path],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout or "(no matches)"
        return output[:4000]
    except Exception as e:
        return f"ERROR: {e}"


def git_log(n: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"ERROR: {e}"


def search_web(query: str) -> str:
    try:
        response = tavily_client.search(query=query, max_results=3)
        results = response.get("results", [])
        return "\n".join(f"- {r['title']}: {r['content'][:200]}" for r in results) or "(no results)"
    except Exception as e:
        return f"ERROR: {e}"


def run_shell(command: str) -> str:
    lowered = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lowered:
            return f"BLOCKED: command matched unsafe pattern '{pattern}'"
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        return output[:4000] if output else "(no output)"
    except Exception as e:
        return f"ERROR: {e}"


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "grep": grep,
    "git_log": git_log,
    "search_web": search_web,
    "run_shell": run_shell,
}

# ---- Tool schemas: what the LLM sees as its "menu" ----

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating or overwriting it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Defaults to current dir"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a text pattern recursively across files in a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "Defaults to current dir"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git commit history for the current repo.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "Number of commits, default 10"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command and return stdout/stderr. Dangerous commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def run_agent(task: str, on_step=None):
    """on_step(step, fn_name, fn_args, result) is called after each tool execution.
    If not provided, falls back to plain print — keeps eval runs and existing
    scripts working unchanged."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a terminal agent with file, search, git, and shell tools. "
                "Use them to complete the task, then give a final plain-text answer. "
                "If a tool returns empty output or an error, report that fact clearly "
                "(e.g. 'no commits found' or 'the file is empty') rather than saying "
                "the task is beyond your capabilities."
            ),
        },
        {"role": "user", "content": task},
    ]

    for step in range(MAX_STEPS):
        response = None
        last_error = None
        for attempt in range(3):  # 1 initial attempt + 2 retries
            try:
                response = client.chat.completions.create(
                    model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto"
                )
                break
            except Exception as e:
                last_error = e
                print(f"[step {step+1}] API error (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    messages.append({
                        "role": "user",
                        "content": "Your last tool call was malformed. Please retry using a valid tool call.",
                    })

        if response is None:
            print(f"[step {step+1}] All 3 attempts failed.")
            return f"AGENT ERROR: failed after 3 attempts — {last_error}"

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                fn_name = call.function.name
                fn_args = json.loads(call.function.arguments) or {}

                result = TOOL_FUNCTIONS[fn_name](**fn_args)

                if on_step:
                    on_step(step + 1, fn_name, fn_args, result)
                else:
                    print(f"[step {step+1}] {fn_name}({fn_args})")

                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "name": fn_name, "content": result}
                )
            continue  # let the model react to the result

        if not on_step:
            print("\n--- FINAL ANSWER ---")
            print(msg.content)
        return msg.content

    print("Max steps reached.")


if __name__ == "__main__":
    task = input("Task: ")
    run_agent(task)