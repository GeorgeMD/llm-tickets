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

| Command            | Usage                                          | Description                                                         |
| :----------------- | :--------------------------------------------- | :------------------------------------------------------------------ |
| **init**           | `ltk init .`                                   | Initializes a `.tickets/` store in the project root.                |
| **epic create**    | `ltk epic create "<name>" [-p/--parent <p>]`   | Creates a new epic, optionally nested under a parent epic.          |
| **epic list**      | `ltk epic list`                                | Lists all epics and their parent associations.                      |
| **epic rename**    | `ltk epic rename <epic> "<new_name>"`          | Renames an epic.                                                    |
| **epic start**     | `ltk epic start <epic>`                        | Marks an epic as in progress.                                       |
| **epic close**     | `ltk epic close <epic>`                        | Closes an epic and unblocks dependent sibling epics.                |
| **epic delete**    | `ltk epic delete <epic>`                       | Deletes an epic and all its nested tickets and sub-epics recursively.|
| **ticket create**  | `ltk ticket create <epic> "<name>"`            | Creates a ticket in an epic. Returns the `xx-xxxxxx` ID.            |
| **ticket list**    | `ltk ticket list <epic>`                       | Lists all tickets for a specific epic in a table view.              |
| **ticket edit**    | `ltk ticket edit <ticket> "<markdown>"`        | Overwrites a ticket's `.md` file content with description.          |
| **ticket show**    | `ltk ticket show <ticket>`                    | Prints the markdown content of a ticket.                            |
| **dep add**        | `ltk dep add <id> <dependencies...>`           | Sets dependencies. Tickets depend on tickets; epics on epics.       |
| **dep rm**         | `ltk dep rm <id> <dependencies...>`            | Removes dependency relationships.                                   |
| **ticket rename**  | `ltk ticket rename <ticket> "<new_name>"`      | Renames a ticket.                                                   |
| **ticket close**   | `ltk ticket close <ticket>`                    | Closes a ticket, automatically unblocking dependent tickets.        |
| **ticket start**   | `ltk ticket start <ticket>`                    | Marks a ticket as in progress.                                      |
| **ticket delete**  | `ltk ticket delete <ticket>`                   | Deletes a ticket and removes it from all dependency lists.          |
| **tree**           | `ltk tree`                                     | Displays the sorted tree of nested epics, tickets, and dependencies.|
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

- Create a parent epic for your feature/milestone:
  ```bash
  ltk epic create "User Authentication"
  # Returns: Created epic epic-a1b2c3 "User Authentication"
  ```
- Create nested sub-epics if needed:
  ```bash
  ltk epic create "OAuth Support" -p epic-a1b2c3
  # Returns: Created epic epic-d4e5f6 "OAuth Support"
  ```
- Create tickets for individual components:
  ```bash
  ltk ticket create epic-d4e5f6 "Implement Login Endpoint"
  # Returns: Created ticket xx-xxxxxx "Implement Login Endpoint" in epic-d4e5f6
  ```

### 3. Setting Up and Removing Dependencies

If a task or epic requires another to be done first, declare the dependency:

- **Epic Dependencies**: Epics can only depend on sibling epics at the same level:
  ```bash
  ltk dep add epic-sibling-b epic-sibling-a
  # Sets epic-sibling-b to [blocked] until epic-sibling-a is closed.
  ```
- **Ticket Dependencies**: Tickets can only depend on other tickets in the same epic:
  ```bash
  ltk dep add ticket-b ticket-a
  # Sets ticket-b to [blocked] until ticket-a is closed.
  ```

To remove a dependency:

```bash
ltk dep rm <identifier> <dependency>
```

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

- **Blocked**: Epics/tickets are automatically marked `[blocked]` if they have unclosed dependencies. Tickets under blocked epics are also automatically effectively blocked.
- **Open**: Active tickets/epics with no open dependencies are marked `[open]`.
- **In Progress**: Mark active items as being worked on:
  ```bash
  ltk epic start <epic id>
  ltk ticket start <ticket id>
  ```
- **Closed**: When complete, close the item to unblock dependent items:
  ```bash
  ltk epic close <epic id>
  ltk ticket close <ticket id>
  ```

### 6. Task Tracking with Steps

Break each ticket into concrete tasks using a `# Steps` section in the ticket
markdown. Prefix a heading with ✅ to mark it as done. `ltk tree` renders tasks with `[x]`/`[ ]` checkboxes (only for open/in-progress tickets).

```markdown
# Steps

## First task
Details about the first task.

## ✅ Second task (already done)
Details about the second task.
```

### 7. Troubleshooting Cycles

If you encounter a `circular dependency` error, rethink the way you split the
work across items to break the cycle.
