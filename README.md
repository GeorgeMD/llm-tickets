# ltk — LLM Ticket Tracking CLI

A lightweight, cross-platform CLI tool for managing epics and tickets in any
project.  Designed for AI agents to coordinate work through a simple `.tickets/`
folder that lives alongside your code.

## Installation

```bash
# From source
pip install -e .

# Or build a standalone executable
pip install pyinstaller
pyinstaller --onefile --name ltk ltk/__main__.py
```

### Prerequisites for Interactive Mode

The interactive tree mode (`ltk tree -i`) requires two command-line tools to be installed and available in your `$PATH`:
- [fzf](https://github.com/junegunn/fzf): For interactive search and navigation.
- [glow](https://github.com/charmbracelet/glow): For rendering ticket markdown content.


## Quick Start

```bash
# Initialise a project
ltk init .

# Create an epic
ltk epic create "Auth System"

# Create tickets
ltk ticket create epic-a1b2c3 "Login endpoint"
ltk ticket create epic-a1b2c3 "Session management"

# Add dependencies (session management depends on login endpoint)
ltk ticket depends c3-x9y8z7 c3-k4m5n6

# Edit a ticket (opens $EDITOR, or pass text directly)
ltk ticket edit c3-x9y8z7 "## Login\n\nImplement OAuth2 flow"

# View the project tree
ltk tree

# Close a ticket (unblocks dependents automatically)
ltk ticket close c3-k4m5n6
```

## Commands

| Command | Description |
|---------|-------------|
| `ltk init <path>` | Initialise a `.tickets/` directory |
| `ltk epic create <name>` | Create a new epic |
| `ltk epic list` | List all epics |
| `ltk epic delete <epic>` | Delete an epic (with confirmation) |
| `ltk epic rename <epic> <new-name>` | Rename an epic |
| `ltk ticket create <epic> <name>` | Create a ticket in an epic |
| `ltk ticket list <epic>` | List tickets in an epic |
| `ltk ticket edit <ticket> [text]` | Edit ticket content |
| `ltk ticket delete <ticket>` | Delete a ticket |
| `ltk ticket depends <ticket> <deps...>` | Add dependencies |
| `ltk ticket rename <ticket> <new-name>` | Rename a ticket |
| `ltk ticket close <ticket>` | Close a ticket |
| `ltk tree` | Show the full project tree |
| `ltk tree -i` | Browse tickets interactively with fzf + glow |


## Identifiers

Epics and tickets can be referenced by:
- **Full ID**: `epic-a1b2c3` or `c3-x9y8z7`
- **ID prefix**: `epic-a1b` or `c3-x9`
- **Epic name** (case-insensitive): `"Auth System"`

## Ticket Statuses

| Status | Meaning |
|--------|---------|
| `open` | Ready to be picked up |
| `in_progress` | Being worked on |
| `blocked` | Depends on an unclosed ticket |
| `closed` | Done — no longer blocks dependents |

## Editing Tickets

The `ticket edit` command supports three input modes:

1. **CLI argument**: `ltk ticket edit TK-ID "some markdown text"`
2. **Piped input**: `echo "# Title" | ltk ticket edit TK-ID`
3. **Editor**: If no text is provided, opens `$EDITOR` (or `$VISUAL`,
   falling back to `notepad` on Windows / `vi` on Unix)

## Data Layout

```
project-root/
└── .tickets/
    ├── .epics.json
    ├── epic-a1b2c3/
    │   ├── .tickets.json
    │   ├── c3-x9y8z7.md
    │   └── c3-k4m5n6.md
    └── epic-d4e5f6/
        ├── .tickets.json
        └── f6-p1q2r3.md
```

## Cross-Platform Distribution

Build a single executable with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --name ltk ltk/__main__.py
# Output: dist/ltk (or dist/ltk.exe on Windows)
```

## License

MIT
