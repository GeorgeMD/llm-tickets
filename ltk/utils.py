"""Utility functions: cycle detection, topological sort, tree rendering, editor."""

import os
import platform
import subprocess
import sys
import tempfile
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple


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


def get_status_priority(status: str) -> int:
    if status == "in_progress":
        return 0
    if status == "open":
        return 1
    if status == "blocked":
        return 2
    if status == "closed":
        return 3
    return 4


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------

def topological_sort(
    tickets: Dict[str, Dict[str, Any]],
    key = None
) -> List[str]:
    """Return ticket IDs in topological order, prioritized by key if provided."""
    # Build in-degree map (only count deps that exist in tickets)
    in_degree: Dict[str, int] = {tid: 0 for tid in tickets}
    adj: Dict[str, List[str]] = {tid: [] for tid in tickets}  # dep -> dependents

    for tid, meta in tickets.items():
        for dep in meta.get("depends", []):
            if dep in tickets:
                in_degree[tid] += 1
                adj[dep].append(tid)

    # Use a list so we can sort by priority at each step
    ready = [tid for tid, deg in in_degree.items() if deg == 0]
    result: List[str] = []

    while ready:
        if key:
            ready.sort(key=key)
        node = ready.pop(0)
        result.append(node)
        for dependent in adj[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)

    # If there are remaining nodes they form a cycle — append them anyway
    remaining = [tid for tid in tickets if tid not in result]
    if key:
        remaining.sort(key=key)
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
    root: "Path",
    epics: Dict[str, Dict[str, Any]],
    tickets_by_epic: Dict[str, Dict[str, Dict[str, Any]]],
    steps_by_ticket: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> str:
    """Render the full project tree as a string.

    *steps_by_ticket* maps ``ticket_id`` to a list of step dicts
    (as returned by ``store.parse_steps``).
    """
    if steps_by_ticket is None:
        steps_by_ticket = {}

    from ltk.store import get_effective_epic_status, get_effective_ticket_status

    def sort_siblings(sibling_dict: Dict[str, Dict[str, Any]]) -> List[str]:
        def key_func(eid):
            meta = sibling_dict[eid]
            eff_status = get_effective_epic_status(root, eid, epics)
            return (get_status_priority(eff_status), meta["name"].lower())
        return topological_sort(sibling_dict, key=key_func)

    def sort_tickets(tickets_dict: Dict[str, Dict[str, Any]], epic_id: str) -> List[str]:
        def key_func(tid):
            meta = tickets_dict[tid]
            eff_status = get_effective_ticket_status(root, epic_id, meta, epics)
            has_deps = 1 if meta.get("depends") else 0
            return (get_status_priority(eff_status), has_deps, meta["name"].lower())
        return topological_sort(tickets_dict, key=key_func)

    def render_epic(epic_id: str, prefix: str, is_top_level: bool, is_last_sibling: bool) -> List[str]:
        meta = epics[epic_id]
        lines = []
        
        eff_status = get_effective_epic_status(root, epic_id, epics)
        label, colour = _STATUS_STYLE.get(eff_status, ("[?]", ""))
        colored_status = _c(colour, label)
        
        if is_top_level:
            epic_line = _c(_BOLD, f"[Epic] {colored_status} {meta['name']}") + _c(_DIM, f" [{epic_id}]")
        else:
            branch = "`-- " if is_last_sibling else "|-- "
            epic_line = f"{prefix}{branch}" + _c(_BOLD, f"[Epic] {colored_status} {meta['name']}") + _c(_DIM, f" [{epic_id}]")
            
        lines.append(epic_line)
        
        if is_top_level:
            cont_prefix = "   "
        else:
            cont_prefix = prefix + ("    " if is_last_sibling else "|   ")
            
        deps = meta.get("depends", [])
        if deps:
            dep_names = []
            for d in deps:
                if d in epics:
                    dep_names.append(f"{d} ({epics[d]['name']})")
                else:
                    dep_names.append(d)
            lines.append(
                _c(_DIM, f"{cont_prefix}-> depends on: {', '.join(dep_names)}")
            )
            
        tickets = tickets_by_epic.get(epic_id, {})
        child_epics = {eid: emeta for eid, emeta in epics.items() if emeta.get("parent") == epic_id}
        
        if not tickets and not child_epics:
            lines.append(_c(_DIM, f"{cont_prefix}(no tickets or sub-epics)"))
        else:
            ordered_tickets = sort_tickets(tickets, epic_id)
            ordered_epics = sort_siblings(child_epics)
            
            children_list = [("ticket", tid) for tid in ordered_tickets] + [("epic", eid) for eid in ordered_epics]
            
            for idx, (kind, item_id) in enumerate(children_list):
                is_last_child = (idx == len(children_list) - 1)
                child_branch = "`-- " if is_last_child else "|-- "
                
                if kind == "ticket":
                    tmeta = tickets[item_id]
                    eff_tstatus = get_effective_ticket_status(root, epic_id, tmeta, epics)
                    tlabel, tcolour = _STATUS_STYLE.get(eff_tstatus, ("[?]", ""))
                    colored_tname = _c(tcolour, f"{tlabel} {tmeta['name']}")
                    
                    ticket_line = f"{cont_prefix}{child_branch}{_c(_DIM, item_id)}  {colored_tname}"
                    lines.append(ticket_line)
                    
                    ticket_cont_prefix = cont_prefix + ("    " if is_last_child else "|   ")
                    
                    tdeps = tmeta.get("depends", [])
                    if tdeps:
                        tdep_names = []
                        for td in tdeps:
                            if td in tickets:
                                tdep_names.append(f"{td} ({tickets[td]['name']})")
                            else:
                                tdep_names.append(td)
                        lines.append(
                            _c(_DIM, f"{ticket_cont_prefix}-> depends on: {', '.join(tdep_names)}")
                        )
                        
                    if eff_tstatus in ("open", "in_progress"):
                        ticket_steps = steps_by_ticket.get(item_id, [])
                        for step in ticket_steps:
                            if step["done"]:
                                check = _c("\033[92m", "[x]")
                                title = _c(_DIM, step["title"])
                            else:
                                check = _c(_DIM, "[ ]")
                                title = step["title"]
                            lines.append(f"{ticket_cont_prefix}{check} {title}")
                            
                elif kind == "epic":
                    lines.extend(render_epic(item_id, prefix=cont_prefix, is_top_level=False, is_last_sibling=is_last_child))
                    
        return lines

    lines: List[str] = []
    top_level_epics = {eid: meta for eid, meta in epics.items() if not meta.get("parent") or meta.get("parent") not in epics}
    top_level_ids = sort_siblings(top_level_epics)
    
    for idx, epic_id in enumerate(top_level_ids):
        lines.extend(render_epic(epic_id, prefix="", is_top_level=True, is_last_sibling=(idx == len(top_level_ids) - 1)))
        if idx < len(top_level_ids) - 1:
            lines.append("")
            
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


def render_epic_interactive(
    epic_id: str,
    prefix: str,
    is_top_level: bool,
    is_last_sibling: bool,
    root: "Path",
    epics: Dict[str, Dict[str, Any]],
    tickets_by_epic: Dict[str, Dict[str, Dict[str, Any]]],
    steps_by_ticket: Dict[str, List[Dict[str, Any]]],
    show_dependencies: bool,
    empty_filepath_str: str,
) -> List[Tuple[str, str]]:
    from ltk.store import get_effective_epic_status, get_effective_ticket_status, get_epic_path
    
    meta = epics[epic_id]
    lines = []
    
    eff_status = get_effective_epic_status(root, epic_id, epics)
    label, colour = _STATUS_STYLE.get(eff_status, ("[?]", ""))
    colored_status = _raw_ansi(colour, label)
    
    if is_top_level:
        epic_line = _raw_ansi(_BOLD, f"[Epic] {colored_status} {meta['name']}") + _raw_ansi(_DIM, f" [{epic_id}]")
    else:
        branch = "`-- " if is_last_sibling else "|-- "
        epic_line = f"{prefix}{branch}" + _raw_ansi(_BOLD, f"[Epic] {colored_status} {meta['name']}") + _raw_ansi(_DIM, f" [{epic_id}]")
        
    lines.append((empty_filepath_str, epic_line))
    
    if is_top_level:
        cont_prefix = "   "
    else:
        cont_prefix = prefix + ("    " if is_last_sibling else "|   ")
        
    if show_dependencies:
        deps = meta.get("depends", [])
        if deps:
            dep_names = []
            for d in deps:
                if d in epics:
                    dep_names.append(f"{d} ({epics[d]['name']})")
                else:
                    dep_names.append(d)
            lines.append((empty_filepath_str, _raw_ansi(_DIM, f"{cont_prefix}-> depends on: {', '.join(dep_names)}")))
            
    tickets = tickets_by_epic.get(epic_id, {})
    child_epics = {eid: emeta for eid, emeta in epics.items() if emeta.get("parent") == epic_id}
    
    def sort_siblings(sibling_dict: Dict[str, Dict[str, Any]]) -> List[str]:
        def key_func(eid):
            smeta = sibling_dict[eid]
            seff_status = get_effective_epic_status(root, eid, epics)
            return (get_status_priority(seff_status), smeta["name"].lower())
        return topological_sort(sibling_dict, key=key_func)

    def sort_tickets(tickets_dict: Dict[str, Dict[str, Any]]) -> List[str]:
        def key_func(tid):
            tmeta = tickets_dict[tid]
            teff_status = get_effective_ticket_status(root, epic_id, tmeta, epics)
            has_deps = 1 if tmeta.get("depends") else 0
            return (get_status_priority(teff_status), has_deps, tmeta["name"].lower())
        return topological_sort(tickets_dict, key=key_func)

    if not tickets and not child_epics:
        lines.append((empty_filepath_str, _raw_ansi(_DIM, f"{cont_prefix}(no tickets or sub-epics)")))
    else:
        ordered_tickets = sort_tickets(tickets)
        ordered_epics = sort_siblings(child_epics)
        
        children_list = [("ticket", tid) for tid in ordered_tickets] + [("epic", eid) for eid in ordered_epics]
        
        for idx, (kind, item_id) in enumerate(children_list):
            is_last_child = (idx == len(children_list) - 1)
            child_branch = "`-- " if is_last_child else "|-- "
            
            if kind == "ticket":
                tmeta = tickets[item_id]
                eff_tstatus = get_effective_ticket_status(root, epic_id, tmeta, epics)
                tlabel, tcolour = _STATUS_STYLE.get(eff_tstatus, ("[?]", ""))
                colored_tname = _raw_ansi(tcolour, f"{tlabel} {tmeta['name']}")
                
                epic_dir = get_epic_path(root, epic_id, epics)
                filepath = str(epic_dir / f"{item_id}.md")
                
                branch_ansi = _raw_ansi(_DIM, cont_prefix + child_branch)
                tid_ansi = _raw_ansi(_DIM, f"({item_id})")
                display = f"{branch_ansi}{colored_tname} {tid_ansi}"
                lines.append((filepath, display))
                
                ticket_cont_prefix = cont_prefix + ("    " if is_last_child else "|   ")
                
                if show_dependencies:
                    tdeps = tmeta.get("depends", [])
                    if tdeps:
                        tdep_names = []
                        for td in tdeps:
                            if td in tickets:
                                tdep_names.append(f"{td} ({tickets[td]['name']})")
                            else:
                                tdep_names.append(td)
                        lines.append((filepath, _raw_ansi(_DIM, f"{ticket_cont_prefix}-> depends on: {', '.join(tdep_names)}")))
                        
                if eff_tstatus in ("open", "in_progress"):
                    ticket_steps = steps_by_ticket.get(item_id, [])
                    for step in ticket_steps:
                        if step["done"]:
                            check = _raw_ansi("\033[92m", "[x]")
                            title = _raw_ansi(_DIM, step["title"])
                        else:
                            check = _raw_ansi(_DIM, "[ ]")
                            title = step["title"]
                        lines.append((filepath, f"{_raw_ansi(_DIM, ticket_cont_prefix)}{check} {title}"))
                        
            elif kind == "epic":
                child_lines = render_epic_interactive(
                    item_id,
                    prefix=cont_prefix,
                    is_top_level=False,
                    is_last_sibling=is_last_child,
                    root=root,
                    epics=epics,
                    tickets_by_epic=tickets_by_epic,
                    steps_by_ticket=steps_by_ticket,
                    show_dependencies=show_dependencies,
                    empty_filepath_str=empty_filepath_str,
                )
                lines.extend(child_lines)
                
    return lines


def run_interactive_tree(
    root: "Path",
    epics: Dict[str, Dict[str, Any]],
    tickets_by_epic: Dict[str, Dict[str, Dict[str, Any]]],
    steps_by_ticket: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    """Launch fzf with glow preview for interactive ticket browsing."""
    from pathlib import Path as _P
    from ltk import store

    # Create an empty file in .tickets/.empty for epic headers/separators preview
    empty_filepath = root / ".empty"
    if not empty_filepath.exists():
        try:
            empty_filepath.touch(exist_ok=True)
        except Exception:
            pass
    empty_filepath_str = str(empty_filepath)

    show_dependencies = False

    while True:
        # Reload status and steps on each iteration
        epics = store.load_epics(root)
        tickets_by_epic = {}
        steps_by_ticket = {}
        for epic_id in epics:
            tickets = store.load_tickets(root, epic_id)
            tickets_by_epic[epic_id] = tickets
            for tid in tickets:
                try:
                    content = store.read_ticket(root, epic_id, tid)
                    steps = store.parse_steps(content)
                    if steps:
                        steps_by_ticket[tid] = steps
                except Exception:
                    pass  # Silently ignore parse failures

        def sort_siblings(sibling_dict: Dict[str, Dict[str, Any]]) -> List[str]:
            from ltk.store import get_effective_epic_status
            def key_func(eid):
                smeta = sibling_dict[eid]
                seff_status = get_effective_epic_status(root, eid, epics)
                return (get_status_priority(seff_status), smeta["name"].lower())
            return topological_sort(sibling_dict, key=key_func)

        top_level_epics = {eid: meta for eid, meta in epics.items() if not meta.get("parent") or meta.get("parent") not in epics}
        top_level_ids = sort_siblings(top_level_epics)
        
        interactive_tuples = []
        for idx, epic_id in enumerate(top_level_ids):
            child_lines = render_epic_interactive(
                epic_id,
                prefix="",
                is_top_level=True,
                is_last_sibling=(idx == len(top_level_ids) - 1),
                root=root,
                epics=epics,
                tickets_by_epic=tickets_by_epic,
                steps_by_ticket=steps_by_ticket,
                show_dependencies=show_dependencies,
                empty_filepath_str=empty_filepath_str,
            )
            interactive_tuples.extend(child_lines)
            if idx < len(top_level_ids) - 1:
                interactive_tuples.append((empty_filepath_str, ""))

        if not interactive_tuples:
            break

        input_text = "\n".join(f"{filepath}\t{display}" for filepath, display in interactive_tuples)

        fzf_cmd = [
            "fzf",
            "--ansi",
            "--delimiter", "\t",
            "--with-nth", "2..",
            "--bind", f"ctrl-h:execute({sys.executable} -m ltk help-menu)+clear-screen",
            "--bind", f"f1:execute({sys.executable} -m ltk help-menu)+clear-screen",
            "--bind", "alt-z:toggle-wrap",
            "--preview", "glow -s dark {1}",
            "--preview-window", "right:60%:wrap:border-left",
            "--header", "Tickets  |  Ctrl+H or F1 for help, Esc to quit\n\n",
            "--no-sort",
            "--reverse",
            "--border", "rounded",
            "--margin", "1,2",
            "--padding", "1",
            "--prompt", "Filter> ",
            "--color", "header:italic:dim",
            "--expect", "ctrl-r,ctrl-d",
        ]

        try:
            result = subprocess.run(
                fzf_cmd, input=input_text, text=True, capture_output=True
            )
            stdout = result.stdout
            if not stdout:
                break

            out_lines = [line.strip() for line in stdout.split("\n") if line.strip()]
            if not out_lines:
                break

            key_or_item = out_lines[0]
            if key_or_item == "ctrl-r":
                continue
            if key_or_item == "ctrl-d":
                show_dependencies = not show_dependencies
                continue

            # It's an item selection (Enter was pressed)
            selected = key_or_item
            # First tab-separated field is the filepath
            filepath = selected.split("\t", 1)[0]
            # Don't open the dummy .empty file (epic headers / separators)
            if filepath and not filepath.endswith(".empty"):
                _open_file_in_editor(filepath)
        except FileNotFoundError:
            raise FileNotFoundError(
                "fzf is required for interactive mode.\n"
                "Install it: https://github.com/junegunn/fzf#installation\n"
                "Also install glow for preview: https://github.com/charmbracelet/glow"
            )


# ---------------------------------------------------------------------------
# Editor support
# ---------------------------------------------------------------------------

def _get_editor() -> str:
    """Return the user's preferred editor command."""
    return (
        os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or ("notepad" if platform.system() == "Windows" else "vi")
    )


def _open_file_in_editor(filepath: str) -> None:
    """Open an existing file in $EDITOR for direct editing."""
    editor = _get_editor()
    try:
        subprocess.run(f'{editor} "{filepath}"', shell=True, check=True)
    except subprocess.CalledProcessError:
        pass


def open_editor(initial_content: str = "") -> Optional[str]:
    """Open $EDITOR with *initial_content* and return the edited text.

    Falls back to notepad (Windows) or vi (Unix).
    Returns None if the user aborts (empty file).
    """
    editor = _get_editor()

    suffix = ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(initial_content)
        tmp_path = tmp.name

    try:
        subprocess.run(f'{editor} "{tmp_path}"', shell=True, check=True)
        with open(tmp_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        return content
    except subprocess.CalledProcessError:
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def get_physical_terminal_size() -> tuple:
    import platform
    import sys
    import os

    if platform.system() == "Windows":
        try:
            import ctypes
            class COORD(ctypes.Structure):
                _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

            class SMALL_RECT(ctypes.Structure):
                _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                            ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

            class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
                _fields_ = [("dwSize", COORD),
                            ("dwCursorPosition", COORD),
                            ("wAttributes", ctypes.c_ushort),
                            ("srWindow", SMALL_RECT),
                            ("dwMaximumWindowSize", COORD)]

            h = ctypes.windll.kernel32.CreateFileW(
                "CONOUT$", 0x40000000 | 0x80000000, 2, None, 3, 0, None
            )
            if h != -1:
                csbi = CONSOLE_SCREEN_BUFFER_INFO()
                success = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, ctypes.byref(csbi))
                ctypes.windll.kernel32.CloseHandle(h)
                if success:
                    cols = csbi.srWindow.Right - csbi.srWindow.Left + 1
                    rows = csbi.srWindow.Bottom - csbi.srWindow.Top + 1
                    return cols, rows
        except Exception:
            pass
    else:
        try:
            import fcntl
            import termios
            import struct
            with open("/dev/tty", "r") as tty:
                h, w = struct.unpack('hh', fcntl.ioctl(tty.fileno(), termios.TIOCGWINSZ, struct.pack('hh', 0, 0)))
                return w, h
        except Exception:
            pass

    # Fallback to standard library
    try:
        import shutil
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns, size.lines
    except Exception:
        return 80, 24


def show_help_menu() -> None:
    """Show interactive help popup centered on terminal."""
    import os
    import sys
    import platform

    # Get direct terminal write stream to ensure visibility under fzf execute
    try:
        if platform.system() == "Windows":
            out = open("CONOUT$", "w", encoding="utf-8")
        else:
            out = open("/dev/tty", "w", encoding="utf-8")
    except Exception:
        out = sys.stdout

    cols, rows = get_physical_terminal_size()

    # Determine encoding compatibility for box drawing characters
    try:
        enc = out.encoding or "utf-8"
        "╔═╗║╚╝─".encode(enc)
        c_tl, c_tr, c_bl, c_br, c_h, c_v, c_s = "╔", "╗", "╚", "╝", "═", "║", "─"
    except Exception:
        c_tl, c_tr, c_bl, c_br, c_h, c_v, c_s = "+", "+", "+", "+", "-", "|", "-"

    help_lines = [
        "LTK INTERACTIVE HELP",
        "SEP",
        "Ctrl+R  : Refresh the view",
        "Ctrl+D  : Toggle ticket dependencies",
        "Alt+Z   : Toggle line wrapping",
        "Arrows  : Navigate the tree",
        "Enter   : Edit selected ticket",
        "Esc     : Quit interactive mode",
        "SEP",
        "Press any key to close"
    ]

    # Calculate dimensions correctly to avoid overflow
    max_len = max(len(line) if line != "SEP" else 20 for line in help_lines)
    box_width = max_len + 6
    box_height = len(help_lines) + 2

    start_row = max(1, (rows - box_height) // 2)
    start_col = max(1, (cols - box_width) // 2)

    # Reset style, switch to alternate screen buffer, and clear screen
    out.write("\033[0m\033[?1049h\033[2J")

    # Top border
    out.write(f"\033[{start_row};{start_col}H")
    out.write(c_tl + c_h * (box_width - 2) + c_tr)

    # Content rows
    for i, line in enumerate(help_lines):
        out.write(f"\033[{start_row + 1 + i};{start_col}H")
        if line == "SEP":
            padded = "".center(box_width - 4, c_s)
        elif ":" in line:
            padded = "  " + line.ljust(box_width - 6)
        else:
            padded = line.center(box_width - 4)
        out.write(c_v + " " + padded + " " + c_v)

    # Bottom border
    out.write(f"\033[{start_row + box_height - 1};{start_col}H")
    out.write(c_bl + c_h * (box_width - 2) + c_br)

    # Move cursor to bottom-right of box to avoid visual clutter
    out.write(f"\033[{start_row + box_height - 2};{start_col + box_width - 3}H")
    out.flush()

    # Drain any pending keypresses in the input buffer first
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        import select
        try:
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)
        except Exception:
            pass

    # Wait for keypress
    try:
        import msvcrt
        msvcrt.getch()
    except ImportError:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if out is not sys.stdout:
        out.close()

