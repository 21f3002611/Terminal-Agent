import click
from agent.tools import run_agent


def format_args(args: dict) -> str:
    """Renders tool args compactly, e.g. path=x.py instead of raw dict repr."""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def make_step_printer(verbose: bool):
    """Returns a callback matching run_agent's on_step signature. Closure over
    `verbose` lets us toggle detail level without changing run_agent at all."""

    def on_step(step, fn_name, fn_args, result):
        click.secho(f"  [{step}] ", fg="cyan", nl=False)
        click.secho(f"{fn_name}", fg="cyan", bold=True, nl=False)
        click.secho(f"({format_args(fn_args)})", fg="cyan")
        if verbose:
            preview = result if len(result) < 300 else result[:300] + "…"
            click.secho(f"      -> {preview}", fg="white", dim=True)

    return on_step


@click.group()
def cli():
    """Terminal Agent — an LLM-powered CLI that can read files, search, and run shell commands."""
    pass


@cli.command()
@click.argument("task", required=False)
@click.option("-v", "--verbose", is_flag=True, help="Show full tool output, not just calls.")
def run(task, verbose):
    """Run a single task. If TASK is omitted, prompts interactively."""
    if not task:
        task = click.prompt("Task")

    click.secho(f"\nTask: {task}\n", fg="yellow", bold=True)

    on_step = make_step_printer(verbose)
    answer = run_agent(task, on_step=on_step)

    click.secho("\n--- Final Answer ---", fg="green", bold=True)
    click.echo(answer)


@cli.command()
def chat():
    """Interactive loop — keep giving tasks until you type 'exit'."""
    click.secho("Terminal Agent — interactive mode (type 'exit' to quit)\n", fg="yellow", bold=True)
    on_step = make_step_printer(verbose=False)
    while True:
        task = click.prompt("Task")
        if task.strip().lower() in ("exit", "quit"):
            break
        answer = run_agent(task, on_step=on_step)
        click.secho("\n--- Final Answer ---", fg="green", bold=True)
        click.echo(answer)
        click.echo()


if __name__ == "__main__":
    cli()