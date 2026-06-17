# Agent Skill: ltk (LLM Ticket Keeping)

This skill enables an AI agent to use the `ltk` command-line tool to manage,
track, and coordinate tasks, epics, and dependencies locally within a project.

## Agent System Prompt Integration

Copy and paste this section into the agent's system prompt to enable `ltk`
capability:

```markdown
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
5. When linking tickets together, the tool checks for circular dependencies.
```

---

## Command Reference

| Command            | Usage                                          | Description                                                         |
| :----------------- | :--------------------------------------------- | :------------------------------------------------------------------ |
| **init**           | `ltk init .`                                   | Initializes a `.tickets/` store in the project root.                |
| **epic create**    | `ltk epic create "<name>"`                     | Creates a new epic. Returns the `epic-xxxxxx` ID.                   |
| **epic list**      | `ltk epic list`                                | Lists all epics and the number of tickets in each.                  |
| **epic rename**    | `ltk epic rename <epic> "<new_name>"`          | Renames an epic.                                                    |
| **epic delete**    | `ltk epic delete <epic>`                       | Deletes an epic and all of its tickets (requires confirmation).     |
| **ticket create**  | `ltk ticket create <epic> "<name>"`            | Creates a ticket in an epic. Returns the `xx-xxxxxx` ID.            |
| **ticket list**    | `ltk ticket list <epic>`                       | Lists all tickets for a specific epic in a table view.              |
| **ticket edit**    | `ltk ticket edit <ticket> "<markdown>"`        | Overwrites a ticket's `.md` file content with description.          |
| **ticket depends** | `ltk ticket depends <ticket> <dep_tickets...>` | Marks a ticket as dependent on others (within the same epic).       |
| **ticket rename**  | `ltk ticket rename <ticket> "<new_name>"`      | Renames a ticket.                                                   |
| **ticket close**   | `ltk ticket close <ticket>`                    | Closes a ticket, automatically unblocking dependent tickets.        |
| **ticket delete**  | `ltk ticket delete <ticket>`                   | Deletes a ticket and removes it from all dependency lists.          |
| **tree**           | `ltk tree`                                     | Displays the hierarchical tree of epics, tickets, and dependencies. |
| **tree -i**        | `ltk tree -i`                                  | Opens the interactive terminal browser using `fzf` and `glow`.      |

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

### 3. Setting Up Dependencies

If a task requires another to be done first, declare the dependency:

```bash
ltk ticket depends <ticket 2 id> <ticket 1 id>
# Sets status of <ticket 2 id> to [blocked] because <ticket 1 id> is not yet closed.
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
- **In Progress**: To mark a ticket as being actively worked on, update the
  epic's `.tickets.json` file directly (under the ticket's `"status"` field, set
  it to `"in_progress"`).
- **Closed**: When a task is complete, run:
  ```bash
  ltk ticket close <ticket 1 id>
  # This automatically unblocks <ticket 2 id>, transitioning its status from [blocked] to [open].
  ```

### 6. Troubleshooting Cycles

If you encounter a `circular dependency` error, rethink the way you split the
work accross tickets to break the cycle.
