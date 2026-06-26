"""Data access layer for the .tickets/ folder structure."""

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TICKETS_DIR = ".tickets"
EPICS_FILE = ".epics.json"
TICKETS_FILE = ".tickets.json"

TICKET_STATUSES = ("open", "in_progress", "blocked", "closed")


# ---------------------------------------------------------------------------
# .tickets root discovery
# ---------------------------------------------------------------------------

def find_tickets_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Walk up from *start_path* (default: cwd) looking for a .tickets/ dir."""
    path = Path(start_path or os.getcwd()).resolve()
    while True:
        candidate = path / TICKETS_DIR
        if candidate.is_dir():
            return candidate
        parent = path.parent
        if parent == path:          # filesystem root
            return None
        path = parent


def require_root() -> Path:
    """Return the .tickets root or exit with a helpful message."""
    root = find_tickets_root()
    if root is None:
        raise FileNotFoundError(
            "No .tickets/ directory found.\n"
            "Run 'ltk init <project_root>' to initialise a project."
        )
    return root


def init_project(project_root: Path) -> Path:
    """Create .tickets/ and seed .epics.json at *project_root*."""
    tickets_path = project_root.resolve() / TICKETS_DIR
    if tickets_path.exists():
        raise FileExistsError(
            f".tickets/ already exists at {project_root.resolve()}"
        )
    tickets_path.mkdir(parents=True)
    _save_json(tickets_path / EPICS_FILE, {})
    return tickets_path


# ---------------------------------------------------------------------------
# Epic helpers
# ---------------------------------------------------------------------------

def load_epics(root: Path) -> Dict[str, Dict[str, Any]]:
    """Return {epic_id: epic_meta} mapping (with migration/normalization)."""
    data = _load_json(root / EPICS_FILE)
    migrated = False
    for eid, value in list(data.items()):
        if isinstance(value, str):
            data[eid] = {
                "name": value,
                "parent": None,
                "status": "open",
                "depends": []
            }
            migrated = True
        else:
            if "parent" not in value:
                value["parent"] = None
                migrated = True
            if "status" not in value:
                value["status"] = "open"
                migrated = True
            if "depends" not in value:
                value["depends"] = []
                migrated = True
    if migrated:
        save_epics(root, data)
    return data


def save_epics(root: Path, data: Dict[str, Dict[str, Any]]) -> None:
    _save_json(root / EPICS_FILE, data)


def get_epic_path(root: Path, epic_id: str, epics_registry: Dict[str, Any]) -> Path:
    """Return the physical Path of an epic by traversing its parent chain."""
    parts = []
    curr = epic_id
    while curr:
        parts.append(curr)
        curr = epics_registry.get(curr, {}).get("parent")
    parts.reverse()
    return root.joinpath(*parts)


def generate_epic_id(existing_ids: set) -> str:
    """Generate a unique epic-<6 hex chars> id."""
    for _ in range(1000):
        eid = f"epic-{secrets.token_hex(3)}"
        if eid not in existing_ids:
            return eid
    raise RuntimeError("Failed to generate a unique epic ID")


def create_epic(root: Path, name: str, parent_id: Optional[str] = None) -> str:
    """Create a new epic folder and register it.  Returns the epic_id."""
    epics = load_epics(root)
    if parent_id and parent_id not in epics:
        raise KeyError(f"Parent epic '{parent_id}' not found")
        
    epic_id = generate_epic_id(set(epics.keys()))
    epics[epic_id] = {
        "name": name,
        "parent": parent_id,
        "status": "open",
        "depends": []
    }
    save_epics(root, epics)
    
    epic_dir = get_epic_path(root, epic_id, epics)
    epic_dir.mkdir(parents=True, exist_ok=True)
    _save_json(epic_dir / TICKETS_FILE, {})
    return epic_id


def delete_epic(root: Path, epic_id: str) -> None:
    """Remove an epic folder recursively and its registry entries."""
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")
        
    # Find all descendants recursively
    to_delete = [epic_id]
    queue = [epic_id]
    while queue:
        curr = queue.pop(0)
        children = [eid for eid, meta in epics.items() if meta.get("parent") == curr]
        to_delete.extend(children)
        queue.extend(children)
        
    epic_dir = get_epic_path(root, epic_id, epics)
    
    # Remove from other epics' dependency lists
    for meta in epics.values():
        deps = meta.get("depends", [])
        if epic_id in deps:
            deps.remove(epic_id)
            
    for eid in to_delete:
        if eid in epics:
            del epics[eid]
            
    save_epics(root, epics)
    
    if epic_dir.exists():
        shutil.rmtree(epic_dir)


def rename_epic(root: Path, epic_id: str, new_name: str) -> None:
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")
    epics[epic_id]["name"] = new_name
    save_epics(root, epics)


def resolve_epic(root: Path, identifier: str) -> Tuple[str, Dict[str, Any]]:
    """Resolve an epic by full ID, ID prefix, or name.  Returns (id, meta)."""
    epics = load_epics(root)

    # exact id
    if identifier in epics:
        return identifier, epics[identifier]

    # prefix match on id
    matches = [
        (eid, meta) for eid, meta in epics.items()
        if eid.startswith(identifier)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous epic identifier '{identifier}'. "
            f"Matches: {', '.join(m[0] for m in matches)}"
        )

    # name match (case-insensitive)
    matches = [
        (eid, meta) for eid, meta in epics.items()
        if meta["name"].lower() == identifier.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous epic name '{identifier}'. "
            f"Matches: {', '.join(m[0] for m in matches)}"
        )

    raise KeyError(f"Epic '{identifier}' not found")


# ---------------------------------------------------------------------------
# Ticket helpers
# ---------------------------------------------------------------------------

def load_tickets(root: Path, epic_id: str) -> Dict[str, Dict[str, Any]]:
    """Return {ticket_id: {name, status, depends}} for an epic."""
    epics = load_epics(root)
    epic_dir = get_epic_path(root, epic_id, epics)
    return _load_json(epic_dir / TICKETS_FILE)


def save_tickets(
    root: Path, epic_id: str, data: Dict[str, Dict[str, Any]]
) -> None:
    epics = load_epics(root)
    epic_dir = get_epic_path(root, epic_id, epics)
    _save_json(epic_dir / TICKETS_FILE, data)


def generate_ticket_id(epic_id: str, existing_ids: set) -> str:
    """Generate <last-2-of-epic>-<6 hex chars>, unique within the epic."""
    prefix = epic_id[-2:]
    for _ in range(1000):
        tid = f"{prefix}-{secrets.token_hex(3)}"
        if tid not in existing_ids:
            return tid
    raise RuntimeError("Failed to generate a unique ticket ID")


def create_ticket(root: Path, epic_id: str, name: str) -> str:
    """Create a ticket .md file and register it.  Returns the ticket_id."""
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")
    tickets = load_tickets(root, epic_id)
    ticket_id = generate_ticket_id(epic_id, set(tickets.keys()))
    tickets[ticket_id] = {
        "name": name,
        "status": "open",
        "depends": [],
    }
    save_tickets(root, epic_id, tickets)
    epic_dir = get_epic_path(root, epic_id, epics)
    ticket_path = epic_dir / f"{ticket_id}.md"
    ticket_path.write_text(f"# {name}\n", encoding="utf-8")
    return ticket_id


def delete_ticket(root: Path, epic_id: str, ticket_id: str) -> None:
    """Delete a ticket file and remove it from the registry and dependencies."""
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")

    # Remove from other tickets' dependency lists
    for meta in tickets.values():
        deps = meta.get("depends", [])
        if ticket_id in deps:
            deps.remove(ticket_id)

    del tickets[ticket_id]
    save_tickets(root, epic_id, tickets)

    epics = load_epics(root)
    epic_dir = get_epic_path(root, epic_id, epics)
    ticket_path = epic_dir / f"{ticket_id}.md"
    if ticket_path.exists():
        ticket_path.unlink()


def rename_ticket(
    root: Path, epic_id: str, ticket_id: str, new_name: str
) -> None:
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")
    tickets[ticket_id]["name"] = new_name
    save_tickets(root, epic_id, tickets)


def edit_ticket(
    root: Path, epic_id: str, ticket_id: str, content: str
) -> None:
    """Overwrite the ticket markdown file with *content*."""
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")
    epics = load_epics(root)
    epic_dir = get_epic_path(root, epic_id, epics)
    ticket_path = epic_dir / f"{ticket_id}.md"
    ticket_path.write_text(content, encoding="utf-8")


def read_ticket(root: Path, epic_id: str, ticket_id: str) -> str:
    epics = load_epics(root)
    epic_dir = get_epic_path(root, epic_id, epics)
    ticket_path = epic_dir / f"{ticket_id}.md"
    if not ticket_path.exists():
        raise FileNotFoundError(f"Ticket file not found: {ticket_path}")
    return ticket_path.read_text(encoding="utf-8-sig")


import re

_STEPS_HEADER_RE = re.compile(r"^#\s+Steps\s*$", re.MULTILINE)
_STEP_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_DONE_PREFIX = "\u2705"  # ✅


def parse_steps(content: str) -> List[Dict[str, Any]]:
    """Extract steps from a ticket's markdown content.

    Looks for a ``# Steps`` H1 section.  Each ``## Title`` under it is a
    step.  Steps whose title starts with the ✅ character are considered
    done.  Returns a list of ``{"title": str, "done": bool}`` dicts, or
    an empty list if parsing fails or no steps section exists.
    """
    # Find the # Steps header
    match = _STEPS_HEADER_RE.search(content)
    if not match:
        return []

    # Content after the # Steps header
    after_steps = content[match.end():]

    # Stop at the next H1 (if any) so we don't bleed into other sections
    next_h1 = re.search(r"^#\s+", after_steps, re.MULTILINE)
    if next_h1:
        after_steps = after_steps[:next_h1.start()]

    steps: List[Dict[str, Any]] = []
    for step_match in _STEP_RE.finditer(after_steps):
        raw_title = step_match.group(1).strip()
        done = raw_title.startswith(_DONE_PREFIX)
        title = raw_title.lstrip(_DONE_PREFIX).strip() if done else raw_title
        steps.append({"title": title, "done": done})

    return steps



def add_dependencies(
    root: Path,
    epic_id: str,
    ticket_id: str,
    dep_ids: List[str],
) -> None:
    """Add dependency edges (within the same epic).  Validates and detects cycles."""
    from ltk.utils import would_create_cycle  # deferred to avoid circular import

    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")

    for dep_id in dep_ids:
        if dep_id not in tickets:
            raise KeyError(
                f"Dependency '{dep_id}' not found in the same epic"
            )
        if dep_id == ticket_id:
            raise ValueError("A ticket cannot depend on itself")

    # Cycle check
    for dep_id in dep_ids:
        if would_create_cycle(tickets, ticket_id, dep_id):
            raise ValueError(
                f"Adding dependency {ticket_id} -> {dep_id} would create "
                f"a circular dependency"
            )

    current_deps = set(tickets[ticket_id].get("depends", []))
    tickets[ticket_id]["depends"] = list(current_deps | set(dep_ids))

    # Set status to blocked if any dependency is not closed
    has_open_dep = any(
        tickets[d]["status"] != "closed"
        for d in tickets[ticket_id]["depends"]
    )
    if has_open_dep:
        tickets[ticket_id]["status"] = "blocked"

    save_tickets(root, epic_id, tickets)


def remove_dependencies(
    root: Path,
    epic_id: str,
    ticket_id: str,
    dep_ids: List[str],
) -> None:
    """Remove dependency edges (within the same epic)."""
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")

    current_deps = tickets[ticket_id].get("depends", [])

    for dep_id in dep_ids:
        if dep_id not in current_deps:
            ticket_name = tickets[ticket_id]["name"]
            dep_name = tickets[dep_id]["name"]
            raise ValueError(
                f"There is no dependency: '{ticket_name}' -> '{dep_name}'"
            )

    updated_deps = [d for d in current_deps if d not in dep_ids]
    tickets[ticket_id]["depends"] = updated_deps

    # If the ticket was blocked, check if it is still blocked
    if tickets[ticket_id]["status"] == "blocked":
        has_open_dep = any(
            tickets[d]["status"] != "closed"
            for d in tickets[ticket_id]["depends"]
            if d in tickets
        )
        if not has_open_dep:
            tickets[ticket_id]["status"] = "open"

    save_tickets(root, epic_id, tickets)




def close_ticket(
    root: Path, epic_id: str, ticket_id: str
) -> List[str]:
    """Close a ticket and unblock dependents whose deps are all closed.

    Returns a list of ticket IDs that were unblocked.
    """
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")

    tickets[ticket_id]["status"] = "closed"

    unblocked: List[str] = []
    for tid, meta in tickets.items():
        if tid == ticket_id:
            continue
        if meta["status"] != "blocked":
            continue
        if ticket_id not in meta.get("depends", []):
            continue
        # All deps closed?
        all_closed = all(
            tickets.get(d, {}).get("status") == "closed"
            for d in meta["depends"]
        )
        if all_closed:
            meta["status"] = "open"
            unblocked.append(tid)

    save_tickets(root, epic_id, tickets)
    return unblocked


def get_effective_epic_status(root: Path, epic_id: str, epics: Dict[str, Any]) -> str:
    """Return the effective status of an epic, taking parent status into account."""
    meta = epics[epic_id]
    if meta["status"] == "closed":
        return "closed"
        
    curr = meta
    while curr:
        if curr["status"] == "blocked":
            return "blocked"
        parent_id = curr.get("parent")
        curr = epics.get(parent_id) if parent_id else None
        
    return meta["status"]


def get_effective_ticket_status(root: Path, epic_id: str, ticket_meta: Dict[str, Any], epics: Dict[str, Any]) -> str:
    """Return the effective status of a ticket, taking epic status into account."""
    if ticket_meta["status"] == "closed":
        return "closed"
    epic_status = get_effective_epic_status(root, epic_id, epics)
    if epic_status == "blocked":
        return "blocked"
    return ticket_meta["status"]


def start_ticket(root: Path, epic_id: str, ticket_id: str) -> bool:
    """Mark a ticket as in progress.

    Returns True if the status was changed, or False if it was already in progress.
    Raises ValueError if the ticket is blocked, closed, or in another invalid state.
    """
    tickets = load_tickets(root, epic_id)
    if ticket_id not in tickets:
        raise KeyError(f"Ticket '{ticket_id}' not found")

    epics = load_epics(root)
    status = get_effective_ticket_status(root, epic_id, tickets[ticket_id], epics)
    if status == "blocked":
        raise ValueError(f"Ticket '{ticket_id}' is blocked")
    if status == "closed":
        raise ValueError(f"Ticket '{ticket_id}' is closed")
    if tickets[ticket_id]["status"] == "in_progress":
        return False

    tickets[ticket_id]["status"] = "in_progress"
    save_tickets(root, epic_id, tickets)
    return True


def start_epic(root: Path, epic_id: str) -> bool:
    """Mark an epic as in progress.

    Returns True if the status was changed, or False if it was already in progress.
    Raises ValueError if the epic is blocked, closed, or in another invalid state.
    """
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")

    eff_status = get_effective_epic_status(root, epic_id, epics)
    if eff_status == "blocked":
        raise ValueError(f"Epic '{epic_id}' is blocked")
    if eff_status == "closed":
        raise ValueError(f"Epic '{epic_id}' is closed")
    if epics[epic_id]["status"] == "in_progress":
        return False

    epics[epic_id]["status"] = "in_progress"
    save_epics(root, epics)
    return True


def close_epic(root: Path, epic_id: str) -> List[str]:
    """Close an epic and unblock dependent sibling epics.

    Returns a list of sibling epic IDs that were unblocked.
    """
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")

    epics[epic_id]["status"] = "closed"

    parent_id = epics[epic_id].get("parent")
    siblings = {eid: meta for eid, meta in epics.items() if meta.get("parent") == parent_id}

    unblocked: List[str] = []
    for eid, meta in siblings.items():
        if eid == epic_id:
            continue
        if meta["status"] != "blocked":
            continue
        if epic_id not in meta.get("depends", []):
            continue
            
        all_closed = all(
            epics.get(d, {}).get("status") == "closed"
            for d in meta["depends"]
        )
        if all_closed:
            meta["status"] = "open"
            unblocked.append(eid)

    save_epics(root, epics)
    return unblocked


def add_epic_dependencies(
    root: Path,
    epic_id: str,
    dep_ids: List[str],
) -> None:
    """Add dependency edges between sibling epics. Validates and detects cycles."""
    from ltk.utils import would_create_cycle  # deferred to avoid circular import

    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")

    parent_id = epics[epic_id].get("parent")
    for dep_id in dep_ids:
        if dep_id not in epics:
            raise KeyError(f"Dependency epic '{dep_id}' not found")
        if epics[dep_id].get("parent") != parent_id:
            raise ValueError("Epics can only depend on other epics at the same level")
        if dep_id == epic_id:
            raise ValueError("An epic cannot depend on itself")

    # Cycle check
    for dep_id in dep_ids:
        if would_create_cycle(epics, epic_id, dep_id):
            raise ValueError(
                f"Adding dependency {epic_id} -> {dep_id} would create "
                f"a circular dependency"
            )

    current_deps = set(epics[epic_id].get("depends", []))
    epics[epic_id]["depends"] = list(current_deps | set(dep_ids))

    # Set status to blocked if any dependency is not closed
    has_open_dep = any(
        epics[d]["status"] != "closed"
        for d in epics[epic_id]["depends"]
    )
    if has_open_dep:
        epics[epic_id]["status"] = "blocked"

    save_epics(root, epics)


def remove_epic_dependencies(
    root: Path,
    epic_id: str,
    dep_ids: List[str],
) -> None:
    """Remove dependency edges between sibling epics."""
    epics = load_epics(root)
    if epic_id not in epics:
        raise KeyError(f"Epic '{epic_id}' not found")

    current_deps = epics[epic_id].get("depends", [])

    for dep_id in dep_ids:
        if dep_id not in current_deps:
            epic_name = epics[epic_id]["name"]
            dep_name = epics[dep_id]["name"]
            raise ValueError(
                f"There is no dependency: '{epic_name}' -> '{dep_name}'"
            )

    updated_deps = [d for d in current_deps if d not in dep_ids]
    epics[epic_id]["depends"] = updated_deps

    if epics[epic_id]["status"] == "blocked":
        has_open_dep = any(
            epics[d]["status"] != "closed"
            for d in epics[epic_id]["depends"]
            if d in epics
        )
        if not has_open_dep:
            epics[epic_id]["status"] = "open"

    save_epics(root, epics)


def resolve_ticket(
    root: Path, identifier: str
) -> Tuple[str, str, Dict[str, Any]]:
    """Resolve a ticket by full ID or prefix across all epics.

    Returns (epic_id, ticket_id, ticket_meta).
    """
    epics = load_epics(root)
    all_matches: List[Tuple[str, str, Dict[str, Any]]] = []

    for epic_id in epics:
        tickets = load_tickets(root, epic_id)
        # exact match
        if identifier in tickets:
            return epic_id, identifier, tickets[identifier]
        # prefix match
        for tid, meta in tickets.items():
            if tid.startswith(identifier):
                all_matches.append((epic_id, tid, meta))

    if len(all_matches) == 1:
        return all_matches[0]
    if len(all_matches) > 1:
        raise ValueError(
            f"Ambiguous ticket identifier '{identifier}'. Matches: "
            + ", ".join(f"{m[1]} (in {m[0]})" for m in all_matches)
        )
    raise KeyError(f"Ticket '{identifier}' not found")


def resolve_ticket_in_epic(
    root: Path, epic_id: str, identifier: str
) -> Tuple[str, Dict[str, Any]]:
    """Resolve a ticket within a specific epic.  Returns (ticket_id, meta)."""
    tickets = load_tickets(root, epic_id)

    if identifier in tickets:
        return identifier, tickets[identifier]

    matches = [
        (tid, meta) for tid, meta in tickets.items()
        if tid.startswith(identifier)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous ticket '{identifier}'. "
            f"Matches: {', '.join(m[0] for m in matches)}"
        )
    raise KeyError(f"Ticket '{identifier}' not found in epic '{epic_id}'")


# ---------------------------------------------------------------------------
# Low-level JSON I/O
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
