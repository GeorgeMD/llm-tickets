"""Utility functions: cycle detection, topological sort, tree rendering, editor."""

import os
import platform
import subprocess
import sys
import tempfile
from collections import deque
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Dependency cycle detection
# ---------------------------------------------------------------------------

def would_create_cycle(
    tickets: Dict[str, Dict[str, Any]],
    ticket_id: str,
    new_dep: str,
) -> bool:
    """Return True if making *ticket_id* depend on *new_dep* creates a cycle.

    A cycle exists iff *ticket_id* is already reachable from *new_dep*
    via existing dependency edges.
    """
    visited: Set[str] = set()
    stack = [new_dep]
    while stack:
        current = stack.pop()
        if current == ticket_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        deps = tickets.get(current, {}).get("depends", [])
        stack.extend(deps)
    return False


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------

def topological_sort(
    tickets: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Return ticket IDs in topological order (no-dependency tickets first).

    Tickets whose dependencies are not in *tickets* are treated as having
    no dependency on that missing ticket.
    """
    # Build in-degree map (only count deps that exist in tickets)
    in_degree: Dict[str, int] = {tid: 0 for tid in tickets}
    adj: Dict[str, List[str]] = {tid: [] for tid in tickets}  # dep -> dependents

    for tid, meta in tickets.items():
        for dep in meta.get("depends", []):
            if dep in tickets:
                in_degree[tid] += 1
                adj[dep].append(tid)

    queue: deque[str] = deque(
        tid for tid, deg in in_degree.items() if deg == 0
    )
    result: List[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in adj[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # If there are remaining nodes they form a cycle — append them anyway
    remaining = [tid for tid in tickets if tid not in result]
    result.extend(remaining)
    return result


# ---------------------------------------------------------------------------
# Tree rendering
# ---------------------------------------------------------------------------

# Status display config: (label, ANSI colour code)
_STATUS_STYLE = {
    "open":        ("[open]",        "\033[92m"),  # bright green
    "in_progress": ("[in progress]", "\033[32m"),  # green (darker)
    "blocked":     ("[blocked]",     "\033[31m"),  # red
    "closed":      ("[closed]",      "\033[90m"),  # grey
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _supports_colour() -> bool:
    """Best-effort check for ANSI colour support."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if platform.system() == "Windows":
        return os.environ.get("TERM") == "xterm" or os.environ.get("WT_SESSION") is not None
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap *text* in ANSI escape if colour is supported."""
    if _supports_colour():
        return f"{code}{text}{_RESET}"
    return text


def format_tree(
    epics: Dict[str, str],
    tickets_by_epic: Dict[str, Dict[str, Dict[str, Any]]],
    steps_by_ticket: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> str:
    """Render the full project tree as a string.

    *steps_by_ticket* maps ``ticket_id`` to a list of step dicts
    (as returned by ``store.parse_steps``).
    """
    if steps_by_ticket is None:
        steps_by_ticket = {}

    lines: List[str] = []
    sorted_epics = sorted(epics.items(), key=lambda x: x[1].lower())

    for idx, (epic_id, epic_name) in enumerate(sorted_epics):
        tickets = tickets_by_epic.get(epic_id, {})
        lines.append(
            _c(_BOLD, f"[Epic] {epic_name}") + _c(_DIM, f" [{epic_id}]")
        )

        if not tickets:
            lines.append(_c(_DIM, "   (no tickets)"))
        else:
            ordered = topological_sort(tickets)
            for i, tid in enumerate(ordered):
                meta = tickets[tid]
                is_last = i == len(ordered) - 1
                branch = "`-- " if is_last else "|-- "
                label, colour = _STATUS_STYLE.get(
                    meta["status"], ("[?]", "")
                )
                colored_name = _c(colour, f"{label} {meta['name']}")
                line = f"   {branch}{_c(_DIM, tid)}  {colored_name}"
                lines.append(line)

                # Continuation prefix for lines under this ticket
                cont_prefix = "       " if is_last else "   |   "

                # Show dependencies
                deps = meta.get("depends", [])
                if deps:
                    dep_names = []
                    for d in deps:
                        if d in tickets:
                            dep_names.append(f"{d} ({tickets[d]['name']})")
                        else:
                            dep_names.append(d)
                    lines.append(
                        _c(_DIM, f"{cont_prefix}-> depends on: {', '.join(dep_names)}")
                    )

                # Show steps (tasks)
                ticket_steps = steps_by_ticket.get(tid, [])
                for step in ticket_steps:
                    if step["done"]:
                        check = _c("\033[92m", "[x]")
                        title = _c(_DIM, step["title"])
                    else:
                        check = _c(_DIM, "[ ]")
                        title = step["title"]
                    lines.append(f"{cont_prefix}{check} {title}")

        if idx < len(sorted_epics) - 1:
            lines.append("")  # blank separator between epics

    return "\n".join(lines)


def format_ticket_list(
    epic_id: str,
    epic_name: str,
    tickets: Dict[str, Dict[str, Any]],
) -> str:
    """Render a table of tickets for a single epic."""
    lines: List[str] = []
    lines.append(_c(_BOLD, f"[Epic] {epic_name}") + _c(_DIM, f" [{epic_id}]"))
    lines.append("")

    if not tickets:
        lines.append(_c(_DIM, "  (no tickets)"))
        return "\n".join(lines)

    # Column widths
    id_w = max(len(tid) for tid in tickets)
    id_w = max(id_w, 2)

    header = f"  {'ID':<{id_w}}  Ticket"
    lines.append(_c(_BOLD, header))
    lines.append(f"  {'-' * id_w}  {'-' * 30}")

    for tid, meta in tickets.items():
        label, colour = _STATUS_STYLE.get(meta["status"], ("[?]", ""))
        colored_name = _c(colour, f"{label} {meta['name']}")
        lines.append(f"  {tid:<{id_w}}  {colored_name}")

    lines.append("")
    lines.append(_c(_DIM, f"  {len(tickets)} ticket(s)"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive fzf + glow browser
# ---------------------------------------------------------------------------

def _raw_ansi(code: str, text: str) -> str:
    """Wrap text in ANSI codes unconditionally (for piping to fzf --ansi)."""
    return f"{code}{text}{_RESET}"


def run_interactive_tree(
    root: "Path",
    epics: Dict[str, str],
    tickets_by_epic: Dict[str, Dict[str, Dict[str, Any]]],
    steps_by_ticket: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    """Launch fzf with glow preview for interactive ticket browsing."""
    from pathlib import Path as _P

    if steps_by_ticket is None:
        steps_by_ticket = {}

    # Create an empty file in .tickets/.empty for epic headers/separators preview
    empty_filepath = root / ".empty"
    if not empty_filepath.exists():
        try:
            empty_filepath.touch(exist_ok=True)
        except Exception:
            pass
    empty_filepath_str = str(empty_filepath)

    lines: List[str] = []
    sorted_epics = sorted(epics.items(), key=lambda x: x[1].lower())

    for idx, (epic_id, epic_name) in enumerate(sorted_epics):
        tickets = tickets_by_epic.get(epic_id, {})
        
        # Add epic header line
        epic_header_display = _raw_ansi(_BOLD, f"[Epic] {epic_name}") + _raw_ansi(_DIM, f" [{epic_id}]")
        lines.append(f"{empty_filepath_str}\t{epic_header_display}")

        if not tickets:
            no_tickets_display = _raw_ansi(_DIM, "   (no tickets)")
            lines.append(f"{empty_filepath_str}\t{no_tickets_display}")
        else:
            ordered = topological_sort(tickets)
            for i, tid in enumerate(ordered):
                meta = tickets[tid]
                filepath = str(_P(root / epic_id / f"{tid}.md"))
                is_last = i == len(ordered) - 1
                branch = "`-- " if is_last else "|-- "
                label, colour = _STATUS_STYLE.get(
                    meta["status"], ("[?]", "")
                )
                colored_label = _raw_ansi(colour, label)
                name_part = meta["name"]
                
                # Format: branch + colored_label + name_part + (tid)
                branch_ansi = _raw_ansi(_DIM, f"   {branch}")
                tid_ansi = _raw_ansi(_DIM, f"({tid})")
                display = f"{branch_ansi}{colored_label} {name_part} {tid_ansi}"
                lines.append(f"{filepath}\t{display}")

                # Show steps (tasks) under the ticket
                cont_prefix = "       " if is_last else "   |   "
                ticket_steps = steps_by_ticket.get(tid, [])
                for step in ticket_steps:
                    if step["done"]:
                        check = _raw_ansi("\033[92m", "[x]")
                        title = _raw_ansi(_DIM, step["title"])
                    else:
                        check = _raw_ansi(_DIM, "[ ]")
                        title = step["title"]
                    step_display = f"{_raw_ansi(_DIM, cont_prefix)}{check} {title}"
                    lines.append(f"{filepath}\t{step_display}")
        
        if idx < len(sorted_epics) - 1:
            lines.append(f"{empty_filepath_str}\t")

    if not lines:
        return

    input_text = "\n".join(lines)

    fzf_cmd = [
        "fzf",
        "--ansi",
        "--delimiter", "\t",
        "--with-nth", "2..",
        "--preview", "glow -s dark {1}",
        "--preview-window", "right:60%:wrap:border-left",
        "--header", "Tickets  |  arrows to navigate, type to filter, Esc to quit\n\n",
        "--no-sort",
        "--reverse",
        "--border", "rounded",
        "--margin", "1,2",
        "--padding", "1",
        "--prompt", "Filter> ",
        "--color", "header:italic:dim",
    ]

    try:
        subprocess.run(fzf_cmd, input=input_text, text=True)
    except FileNotFoundError:
        raise FileNotFoundError(
            "fzf is required for interactive mode.\n"
            "Install it: https://github.com/junegunn/fzf#installation\n"
            "Also install glow for preview: https://github.com/charmbracelet/glow"
        )


# ---------------------------------------------------------------------------
# Editor support
# ---------------------------------------------------------------------------

def open_editor(initial_content: str = "") -> Optional[str]:
    """Open $EDITOR with *initial_content* and return the edited text.

    Falls back to notepad (Windows) or vi (Unix).
    Returns None if the user aborts (empty file).
    """
    editor = (
        os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or ("notepad" if platform.system() == "Windows" else "vi")
    )

    suffix = ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(initial_content)
        tmp_path = tmp.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        return content
    except subprocess.CalledProcessError:
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
