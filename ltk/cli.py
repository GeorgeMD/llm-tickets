"""CLI entry point for ltk — LLM Ticket Tracking."""

import sys

import click

from ltk import store, utils


def _handle_error(func):
    """Decorator that catches known exceptions and prints clean errors."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as exc:
            click.echo(click.style(f"Error: {exc}", fg="red"), err=True)
            raise SystemExit(1)
        except FileExistsError as exc:
            click.echo(click.style(f"Error: {exc}", fg="red"), err=True)
            raise SystemExit(1)
        except (KeyError, ValueError) as exc:
            click.echo(click.style(f"Error: {exc}", fg="red"), err=True)
            raise SystemExit(1)

    return wrapper


# ── Top-level group ────────────────────────────────────────────────────────

@click.group()
@click.version_option(package_name="llm-tickets")
def main():
    """ltk — LLM Ticket Tracking CLI."""


# ── init ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("project_root", type=click.Path(exists=True, file_okay=False))
@_handle_error
def init(project_root):
    """Initialise a .tickets/ directory at PROJECT_ROOT."""
    from pathlib import Path

    path = store.init_project(Path(project_root))
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Initialised ticket store at {path}"
    )


# ── epic group ─────────────────────────────────────────────────────────────

@main.group()
def epic():
    """Manage epics."""


@epic.command("create")
@click.argument("name")
@_handle_error
def epic_create(name):
    """Create a new epic."""
    root = store.require_root()
    epic_id = store.create_epic(root, name)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Created epic {click.style(epic_id, bold=True)} \"{name}\""
    )


@epic.command("list")
@_handle_error
def epic_list():
    """List all epics."""
    root = store.require_root()
    epics = store.load_epics(root)
    if not epics:
        click.echo(click.style("No epics found.", fg="yellow"))
        return
    # Column widths
    id_w = max(len(eid) for eid in epics)
    for eid, name in sorted(epics.items(), key=lambda x: x[1].lower()):
        ticket_count = len(store.load_tickets(root, eid))
        click.echo(
            f"  {click.style(eid, bold=True):<{id_w + 8}}  {name}  "
            f"{click.style(f'({ticket_count} tickets)', dim=True)}"
        )


@epic.command("delete")
@click.argument("epic_identifier")
@_handle_error
def epic_delete(epic_identifier):
    """Delete an epic and all its tickets."""
    root = store.require_root()
    epic_id, epic_name = store.resolve_epic(root, epic_identifier)
    tickets = store.load_tickets(root, epic_id)
    click.echo(
        f"About to delete epic {click.style(epic_id, bold=True)} "
        f"\"{epic_name}\" with {len(tickets)} ticket(s)."
    )
    if not click.confirm("Are you sure?"):
        click.echo("Aborted.")
        return
    store.delete_epic(root, epic_id)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Deleted epic {epic_id}"
    )


@epic.command("rename")
@click.argument("epic_identifier")
@click.argument("new_name")
@_handle_error
def epic_rename(epic_identifier, new_name):
    """Rename an epic."""
    root = store.require_root()
    epic_id, old_name = store.resolve_epic(root, epic_identifier)
    store.rename_epic(root, epic_id, new_name)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Renamed {epic_id}: \"{old_name}\" -> \"{new_name}\""
    )


# ── ticket group ───────────────────────────────────────────────────────────

@main.group()
def ticket():
    """Manage tickets."""


@ticket.command("create")
@click.argument("epic_identifier")
@click.argument("name")
@_handle_error
def ticket_create(epic_identifier, name):
    """Create a new ticket in an epic."""
    root = store.require_root()
    epic_id, epic_name = store.resolve_epic(root, epic_identifier)
    ticket_id = store.create_ticket(root, epic_id, name)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Created ticket {click.style(ticket_id, bold=True)} "
        + f"\"{name}\" in {epic_id}"
    )


@ticket.command("list")
@click.argument("epic_identifier")
@_handle_error
def ticket_list(epic_identifier):
    """List all tickets in an epic."""
    root = store.require_root()
    epic_id, epic_name = store.resolve_epic(root, epic_identifier)
    tickets = store.load_tickets(root, epic_id)
    output = utils.format_ticket_list(epic_id, epic_name, tickets)
    click.echo(output)


@ticket.command("edit")
@click.argument("ticket_identifier")
@click.argument("text", required=False, default=None)
@_handle_error
def ticket_edit(ticket_identifier, text):
    """Edit a ticket's content.

    TEXT can be provided as a CLI argument, piped via stdin, or
    entered interactively in $EDITOR.
    """
    root = store.require_root()
    epic_id, ticket_id, meta = store.resolve_ticket(root, ticket_identifier)

    content = None

    # Mode 1: CLI argument
    if text is not None:
        content = text

    # Mode 2: piped stdin
    elif not sys.stdin.isatty():
        content = sys.stdin.read()

    # Mode 3: open editor
    else:
        existing = store.read_ticket(root, epic_id, ticket_id)
        content = utils.open_editor(existing)
        if content is None:
            click.echo("Editor exited with an error. Aborted.")
            return

    store.edit_ticket(root, epic_id, ticket_id, content)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Updated {ticket_id} \"{meta['name']}\""
    )


@ticket.command("delete")
@click.argument("ticket_identifier")
@_handle_error
def ticket_delete(ticket_identifier):
    """Delete a ticket."""
    root = store.require_root()
    epic_id, ticket_id, meta = store.resolve_ticket(root, ticket_identifier)
    store.delete_ticket(root, epic_id, ticket_id)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Deleted ticket {ticket_id} \"{meta['name']}\""
    )


@ticket.command("depends")
@click.argument("ticket_identifier")
@click.argument("dependencies", nargs=-1, required=True)
@_handle_error
def ticket_depends(ticket_identifier, dependencies):
    """Mark a ticket as depending on one or more other tickets.

    Dependencies must be within the same epic.
    """
    root = store.require_root()
    epic_id, ticket_id, meta = store.resolve_ticket(root, ticket_identifier)

    # Resolve each dependency within the same epic
    resolved_deps = []
    for dep_ident in dependencies:
        dep_id, _ = store.resolve_ticket_in_epic(root, epic_id, dep_ident)
        resolved_deps.append(dep_id)

    store.add_dependencies(root, epic_id, ticket_id, resolved_deps)

    dep_names = ", ".join(resolved_deps)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"{ticket_id} now depends on: {dep_names}"
    )


@ticket.command("rename")
@click.argument("ticket_identifier")
@click.argument("new_name")
@_handle_error
def ticket_rename(ticket_identifier, new_name):
    """Rename a ticket."""
    root = store.require_root()
    epic_id, ticket_id, meta = store.resolve_ticket(root, ticket_identifier)
    old_name = meta["name"]
    store.rename_ticket(root, epic_id, ticket_id, new_name)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Renamed {ticket_id}: \"{old_name}\" -> \"{new_name}\""
    )


@ticket.command("close")
@click.argument("ticket_identifier")
@_handle_error
def ticket_close(ticket_identifier):
    """Close a ticket and unblock dependents."""
    root = store.require_root()
    epic_id, ticket_id, meta = store.resolve_ticket(root, ticket_identifier)
    unblocked = store.close_ticket(root, epic_id, ticket_id)
    click.echo(
        click.style("[ok] ", fg="green")
        + f"Closed {ticket_id} \"{meta['name']}\""
    )
    if unblocked:
        for uid in unblocked:
            tickets = store.load_tickets(root, epic_id)
            uname = tickets[uid]["name"]
            click.echo(
                click.style("  >> ", fg="cyan")
                + f"Unblocked {uid} \"{uname}\""
            )


# ── tree ───────────────────────────────────────────────────────────────────

@main.command()
@click.option("-i", "--interactive", is_flag=True, help="Browse tickets interactively with fzf + glow.")
@_handle_error
def tree(interactive):
    """Display the project tree of epics and tickets."""
    root = store.require_root()
    epics = store.load_epics(root)
    if not epics:
        click.echo(click.style("No epics found.", fg="yellow"))
        return

    tickets_by_epic = {}
    for epic_id in epics:
        tickets_by_epic[epic_id] = store.load_tickets(root, epic_id)

    if interactive:
        utils.run_interactive_tree(root, epics, tickets_by_epic)
    else:
        output = utils.format_tree(epics, tickets_by_epic)
        click.echo(output)
