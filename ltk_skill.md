---
name: ltk
description: Manage your work broken down in epics, tickets and tasks using the "ltk" command line tool.
---

# ltk (LLM Ticket Keeping)

You have access to the `ltk` command-line tool for ticket and dependency
tracking. Use `ltk` to manage your goals, epics, and tasks. Always verify if a
ticket exists before starting work, update ticket content as you make progress,
and close tickets when you finish tasks.

Core guidelines for using `ltk`:

1. Check ticket tree at start of session: `ltk tree`
2. Update ticket descriptions with your design plans and progress via
   `ltk ticket edit <id> "content"`.
3. Avoid interactive terminal editors; always pass the markdown text as an
   argument or pipe it.
4. Ask the user before closing tickets to ensure they are finished before moving
   on, unless the user specifically mentions you can close tickets
   automatically: `ltk ticket close <id>`.
5. Tickets that depend on each other should be linked with `ltk dep add` in
   order to keep track of what can be worked on next.
6. When linking tickets together, the tool checks for circular dependencies.
7. You should update the ticket markdown file when a task is complete to keep
   track of the progress of a ticket.

---

## Command Reference

| Command           | Usage                                     | Description                                                         |
| :---------------- | :---------------------------------------- | :------------------------------------------------------------------ |
| **init**          | `ltk init .`                              | Initializes a `.tickets/` store in the project root.                |
| **epic create**   | `ltk epic create "<name>"`                | Creates a new epic. Returns the `epic-xxxxxx` ID.                   |
| **epic list**     | `ltk epic list`                           | Lists all epics and the number of tickets in each.                  |
| **epic rename**   | `ltk epic rename <epic> "<new_name>"`     | Renames an epic.                                                    |
| **epic delete**   | `ltk epic delete <epic>`                  | Deletes an epic and all of its tickets (requires confirmation).     |
| **ticket create** | `ltk ticket create <epic> "<name>"`       | Creates a ticket in an epic. Returns the `xx-xxxxxx` ID.            |
| **ticket list**   | `ltk ticket list <epic>`                  | Lists all tickets for a specific epic in a table view.              |
| **ticket edit**   | `ltk ticket edit <ticket> "<markdown>"`   | Overwrites a ticket's `.md` file content with description.          |
| **ticket show**   | `ltk ticket show <ticket>`               | Prints the markdown content of a ticket.                            |
| **dep add**       | `ltk dep add <ticket> <dep_tickets...>`   | Marks a ticket as dependent on others (within the same epic).       |
| **dep rm**        | `ltk dep rm <ticket> <dep_tickets...>`    | Removes dependency relationships between tickets.                   |
| **ticket rename** | `ltk ticket rename <ticket> "<new_name>"` | Renames a ticket.                                                   |
| **ticket close**  | `ltk ticket close <ticket>`               | Closes a ticket, automatically unblocking dependent tickets.        |
| **ticket start**  | `ltk ticket start <ticket>`               | Marks a ticket as in progress.                                      |
| **ticket delete** | `ltk ticket delete <ticket>`              | Deletes a ticket and removes it from all dependency lists.          |
| **tree**          | `ltk tree`                                | Displays the hierarchical tree of epics, tickets, and dependencies. |
| **tree -i**       | `ltk tree -i`                             | Opens the interactive terminal browser using `fzf` and `glow`.      |

---

## Agent Operational Workflows

### 1. Initializing and Discovering the Task Board

At the start of any coding task:

- Run `ltk tree` to inspect the project's task board.
- If it outputs `Error: No .tickets/ directory found.`, initialize it:
  ```bash
  ltk init <project root>
  ```

### 2. Creating Epics and Tickets

Break down your work into manageable tasks:

- Create an epic for your feature/milestone:
  ```bash
  ltk epic create "User Authentication"
  # Returns: Created epic <epic id> "User Authentication" in .tickets
  ```
- Create tickets for individual components:
  ```bash
  ltk ticket create <epic id> "Implement Login Endpoint"
  # Returns: Created ticket <ticket 1 id> "Implement Login Endpoint" in <epic id>

  ltk ticket create <epic id> "Implement Session Management"
  # Returns: Created ticket <ticket 2 id> "Implement Session Management" in <epic id>
  ```

### 3. Setting Up and Removing Dependencies

If a task requires another to be done first, declare the dependency:

```bash
ltk dep add <ticket 2 id> <ticket 1 id>
# Sets ticket 1 as a dependency of ticket 2. So ticket 2 will be marked as [blocked] until ticket 1 is closed.
```

To remove a dependency:

```bash
ltk dep rm <ticket 2 id> <ticket 1 id>
# Removes the dependency of ticket 2 on ticket 1. Only useful when you link 2 tickets by mistake.
```

_Note: Dependencies are only supported within the same epic._

### 4. Updating Ticket Descriptions

Always document your plan inside the ticket's Markdown file. Do not run
interactive edit mode (which opens `$EDITOR`). Instead, pass the content
directly or pipe it:

```bash
# Option A: Command-line string
ltk ticket edit <ticket id> "## Requirements\n- Verify passwords using bcrypt\n- Return JWT token on success"

# Option B: Piped input
echo -e "## Requirements\n- Verify passwords using bcrypt\n- Return JWT token on success" | ltk ticket edit <ticket id>
```

### 5. Managing Status Updates

- **Blocked**: Tickets with unclosed dependencies are automatically marked
  `[blocked]`.
- **Open**: Tickets with no dependencies, or whose dependencies are all closed,
  are marked `[open]`.
- **In Progress**: To mark a ticket as being actively worked on, run:
  ```bash
  ltk ticket start <ticket id>
  ```
- **Closed**: When a task is complete, run:
  ```bash
  ltk ticket close <ticket 1 id>
  # This automatically unblocks <ticket 2 id>, transitioning its status from [blocked] to [open].
  ```

### 6. Task Tracking with Steps

Break each ticket into concrete tasks using a `# Steps` section in the ticket
markdown. Each `##` heading under `# Steps` is a task. Prefix a heading with ✅
to mark it as done. `ltk tree` will render tasks with `[x]`/`[ ]` checkboxes (only for tickets in the `open` status).

When editing a ticket, structure it like this:

```bash
ltk ticket edit <ticket id> "# Ticket Title

Description of the work to be done.

# Steps

## First task

Details about the first task.

## ✅ Second task (already done)

Details about the second task.

## Third task

Details about the third task."
```

Each task can contain rich markdown (paragraphs, code blocks, lists, H3+
sub-headings) under its `##` heading. `ltk tree` output will show:

```
[Epic] Backend [epic-a1b2c3]
   `-- c3-x9y8z7  [open] Ticket Title
       [ ] First task
       [x] Second task (already done)
       [ ] Third task
```

### 7. Troubleshooting Cycles

If you encounter a `circular dependency` error, rethink the way you split the
work accross tickets to break the cycle.
