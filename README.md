# Terminal Agent

An LLM-powered CLI agent that understands natural language tasks and executes them using real
file, search, git, and shell tools — via an agentic think → act → observe loop, not a single
prompt-response call.

```
$ tagent run "find all Python files modified today and summarize what they do"
  [1] run_shell(command='find . -name "*.py" -mtime -1')
  [2] read_file(path='agent/tools.py')
  [2] read_file(path='agent/cli.py')

--- Final Answer ---
Two files were modified today: tools.py (defines the 7 tools and the agent loop)
and cli.py (the Click-based command-line interface with colored output).
```

---

## Why this exists

This is Project 2 of a 7-project AI engineering portfolio sprint, built to demonstrate the core
skill behind every production coding agent (Claude Code, Cursor, Devin, etc.): **tool calling +
an agent loop**, not just prompting a model and printing its answer.

## What it's built with

| Piece | Choice | Why |
|---|---|---|
| Inference | [Groq](https://groq.com) (`llama-3.3-70b-versatile`) | Free tier, fast, OpenAI-compatible tool-calling API |
| CLI framework | [Click](https://click.palletsprojects.com) | Declarative commands, `--help` generation, real `pip install`-able entry point |
| Web search | [Tavily](https://tavily.com) | Built specifically for LLM agents, simple API, free tier |
| Packaging | `setup.py` (legacy, not PEP 517) | See "Known issues" below for why |
| Benchmarking | [Harbor](https://github.com/harbor-framework/harbor) / [Terminal-Bench 2.0](https://www.tbench.ai) | Industry-standard agent benchmark |

---

## How it works

### The core idea: tool calling, not autocomplete

A chat model only ever produces text. An **agent** additionally gets a menu of tools it can ask
to have executed on its behalf:

1. The model receives a task and a list of tool schemas (name, description, JSON parameters).
2. It replies with either a final answer, or a request to call a tool (e.g.
   `read_file(path="x.py")`).
3. Your code — never the model itself — actually executes that tool and returns the result.
4. The result is appended to the conversation, and the model is asked again: answer, or call
   another tool?

This repeats until the model gives a final plain-text answer or a hard step cap (`MAX_STEPS = 10`)
is hit, which exists specifically so a confused agent can't loop (and burn API cost) forever.

### The 7 tools

| Tool | Does | Notes |
|---|---|---|
| `read_file` | Reads a file, truncated to 4000 chars | Prevents one huge file from blowing the context window |
| `write_file` | Writes/overwrites a file | The first tool with real side effects — treated more carefully |
| `list_dir` | Lists a directory | |
| `grep` | Wraps the real `grep` binary | Reuses a battle-tested tool instead of reimplementing search |
| `git_log` | Shows recent commits | |
| `search_web` | Live web search via Tavily | |
| `run_shell` | Runs a shell command | Passes through a safety blacklist first (see below) |

### Safety: the blacklist

`run_shell` checks every command against a blocklist (`rm -rf`, `sudo`, `mkfs`, fork bombs,
`curl \| sh`, etc.) before executing anything. This is a **blocklist, not a sandbox** — it stops
obvious disasters, not a determined attacker — but it's a real, tested safety layer: task 8 in
the eval suite calls `run_shell("rm -rf /")` directly (bypassing the LLM) and asserts it comes
back `BLOCKED`, so this isn't just a claim, it's a checked invariant.

### Handling model unreliability

Groq's function-calling occasionally emits malformed tool-call syntax (e.g.
`<function=read_file{"path": "x"}></function>` instead of valid JSON), which the API rejects
outright. Rather than crash, `run_agent` retries up to 3 attempts total, nudging the model to
retry with valid syntax each time. This took the eval pass rate from a flaky 80% up to a
consistent 100% across runs — see [Eval Results](#eval-results) below.

---

## Setup

```bash
git clone https://github.com/21f3002611/Terminal-Agent.git
cd Terminal-Agent
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e . --no-use-pep517  # see "Known issues" for why this flag is needed
```

Create a `.env` file (or export directly) with:
```
GROQ_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

---

## Usage

Once installed, `tagent` is a real command — no need to run Python files directly:

```bash
tagent run "list the files in this directory"
tagent run "list the files here" --verbose      # show full tool output, not just calls
tagent chat                                     # interactive loop, type 'exit' to quit
```

---

## Eval Results

10-task suite mixing deterministic checks (exact/substring match, and — for the safety test —
a **direct function call bypassing the LLM entirely**) with LLM-as-judge for open-ended tasks.

**Pass rate: 10/10 (100%)** after adding the 3-attempt retry logic for malformed tool calls.

| # | Task | Check type | Result |
|---|------|-----------|--------|
| 1 | List files in a directory | substring match | PASS |
| 2 | Read file, report first line | substring match | PASS |
| 3 | Grep pattern, report match count | LLM judge | PASS |
| 4 | Write file, verify on disk | direct file read | PASS |
| 5 | Show git log (no repo present) | LLM judge | PASS |
| 6 | Web search + summarize | LLM judge | PASS |
| 7 | Multi-tool chaining (list + read) | substring match | PASS |
| 8 | Blacklist blocks `rm -rf /` | direct function call (bypasses LLM) | PASS |
| 9 | Run shell command, report output | substring match | PASS |
| 10 | Explain a function from source | LLM judge | PASS |

**Before the retry fix:** the same suite scored 80–90% across runs, with the only failures being
Groq's Llama model occasionally emitting malformed tool-call syntax. This was a genuine,
reproducible model-reliability issue — not a bug in tool dispatch or agent logic, both of which
were passing consistently even on the flaky runs. Bumping from 1 retry to 3 attempts resolved it.

---

## Terminal-Bench 2.0 Integration

Integrated with [Harbor](https://github.com/harbor-framework/harbor), the official harness for
[Terminal-Bench 2.0](https://www.tbench.ai) — 89 hard, realistic CLI tasks in isolated Docker
sandboxes (frontier agents average under 65% overall on this benchmark).

`harbor_agent.py` implements Harbor's `BaseAgent` interface:
- **`setup()`** clones this repo and installs it *inside the task's sandbox container*
- **`run()`** invokes `tagent run "<instruction>"` inside that same sandbox, so every tool call
  operates on the task's own filesystem exactly as it would locally

```bash
export PYTHONPATH=$(pwd)
harbor run -d terminal-bench/terminal-bench-2 \
  --agent harbor_agent:TerminalAgentAdapter \
  -l 1 \
  --ae GROQ_API_KEY=$GROQ_API_KEY --ae TAVILY_API_KEY=$TAVILY_API_KEY
```

**Result of a single-task integration run** (`make-mips-interpreter` — build a MIPS CPU
interpreter that boots a DOOM ROM and renders a frame):

| Stage | Duration | Result |
|---|---|---|
| Environment setup | ~3s | OK |
| Agent setup (clone + install) | ~8s | OK |
| Agent execution | ~6s | Completed, exit code 0 |
| Verifier | ~46s | Reward: 0.0 |

The `0.0` reward reflects task difficulty, not a broken integration — `make-mips-interpreter` is
a large, multi-file systems-programming task, well outside a 10-step file/shell agent's scope.
The pipeline itself — repo clone, install, execution inside an isolated Docker sandbox, automated
scoring — completed without a single error, confirming correct integration with Harbor's
evaluation framework. A broader multi-task run wasn't pursued given the time/cost tradeoff at
this stage of the portfolio.

---

## Known issues / limitations

- **Model tool-call reliability**: Groq's Llama models occasionally emit malformed function-call
  syntax. Mitigated with a 3-attempt retry, not eliminated — a known characteristic of this
  model family, not this codebase.
- **Packaging uses legacy `setup.py`**, not a `pyproject.toml` build backend. This machine's
  system-level `setuptools` had a broken PEP 517 hook (`ModuleNotFoundError:
  setuptools.backends`) that made modern editable installs fail; `setup.py` + `--no-use-pep517`
  sidesteps it entirely. Worth revisiting on a clean environment.
- **`run_shell`'s blacklist is a blocklist, not a sandbox.** It stops known-dangerous patterns
  but isn't a substitute for real containerized isolation — which is exactly why the
  Terminal-Bench integration matters: it runs this same agent inside real Docker sandboxes.

---

## Project structure

```
terminal-agent/
├── agent/
│   ├── tools.py          # 7 tools, schemas, and the core agent loop
│   ├── cli.py             # Click CLI (tagent run / tagent chat)
│   └── eval/
│       ├── tasks.py        # 10 eval task definitions
│       ├── judge.py        # LLM-as-judge for open-ended tasks
│       ├── run_evals.py     # Eval runner
│       └── fixtures/        # Deterministic test files
├── harbor_agent.py        # Terminal-Bench 2.0 / Harbor integration adapter
├── setup.py                # Packaging (see "Known issues")
├── requirements.txt
└── .env                    # GROQ_API_KEY, TAVILY_API_KEY (not committed)
```