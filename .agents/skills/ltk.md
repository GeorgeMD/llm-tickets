# Agent Skill: ltk (LLM Ticket Keeping)

This skill enables an AI agent to use the `ltk` command-line tool to manage, track, and coordinate tasks, epics, and dependencies locally within a project.

## Agent System Prompt Integration
Copy and paste this section into the agent's system prompt to enable `ltk` capability:

```markdown
You have access to the `ltk` command-line tool for ticket and dependency tracking.
Use `ltk` to manage your goals, epics, and tasks. Always verify if a ticket exists before starting work, update ticket content as you make progress, and close tickets when you finish tasks.

Core guidelines for using `ltk`:
1. Check ticket tree at start of session: `ltk tree`
2. Use short ID prefixes (e.g., `b9-57` or `epic-2b`) instead of typing full IDs.
3. Update ticket descriptions with your design plans and progress via `ltk ticket edit <id> "content"`.
4. Avoid interactive terminal editors; always pass the markdown text as an argument or pipe it.
5. Close completed tickets immediately to unblock dependent tasks: `ltk ticket close <id>`.
```

---

## Command Reference

| Command | Usage | Description |
| :--- | :--- | :--- |
| **init** | `ltk init .` | Initializes a `.tickets/` store in the project root. |
| **epic create** | `ltk epic create "<name>"` | Creates a new epic. Returns the `epic-xxxxxx` ID. |
| **epic list** | `ltk epic list` | Lists all epics and the number of tickets in each. |
| **epic rename** | `ltk epic rename <epic> "<new_name>"` | Renames an epic. |
| **epic delete** | `ltk epic delete <epic>` | Deletes an epic and all of its tickets (requires confirmation). |
| **ticket create** | `ltk ticket create <epic> "<name>"` | Creates a ticket in an epic. Returns the `xx-xxxxxx` ID. |
| **ticket list** | `ltk ticket list <epic>` | Lists all tickets for a specific epic in a table view. |
| **ticket edit** | `ltk ticket edit <ticket> "<markdown>"` | Overwrites a ticket's `.md` file content with description. |
| **dep add** | `ltk dep add <ticket> <dep_tickets...>` | Marks a ticket as dependent on others (within the same epic). |
| **dep rm** | `ltk dep rm <ticket> <dep_tickets...>` | Removes dependency relationships between tickets. |
| **ticket rename** | `ltk ticket rename <ticket> "<new_name>"` | Renames a ticket. |
| **ticket close** | `ltk ticket close <ticket>` | Closes a ticket, automatically unblocking dependent tickets. |
| **ticket delete** | `ltk ticket delete <ticket>` | Deletes a ticket and removes it from all dependency lists. |
| **tree** | `ltk tree` | Displays the hierarchical tree of epics, tickets, and dependencies. |
| **tree -i** | `ltk tree -i` | Opens the interactive terminal browser using `fzf` and `glow`. |

---

## Agent Operational Workflows

### 1. Initializing and Discovering the Task Board
At the start of any coding task:
* Run `ltk tree` to inspect the project's task board.
* If it outputs `Error: No .tickets/ directory found.`, initialize it:
  ```bash
  ltk init .
  ```

### 2. Creating Epics and Tickets
Break down your work into manageable tasks:
* Create an epic for your feature/milestone:
  ```bash
  ltk epic create "User Authentication"
  # Returns: Created epic epic-2bdab9 "User Authentication" in .tickets
  ```
* Create tickets for individual components:
  ```bash
  ltk ticket create epic-2bdab9 "Implement Login Endpoint"
  # Returns: Created ticket b9-9b7d48 "Implement Login Endpoint" in epic-2bdab9
  
  ltk ticket create epic-2bdab9 "Implement Session Management"
  # Returns: Created ticket b9-571801 "Implement Session Management" in epic-2bdab9
  ```

### 3. Setting Up and Removing Dependencies
If a task requires another to be done first, declare the dependency:
```bash
ltk dep add b9-571801 b9-9b7d48
# Sets status of b9-571801 to [blocked] because b9-9b7d48 is not yet closed.
```

To remove a dependency:
```bash
ltk dep rm b9-571801 b9-9b7d48
# Removes the dependency of ticket 2 on ticket 1, unblocking ticket 2 if no other open dependencies remain.
```
*Note: Dependencies are only supported within the same epic.*

### 4. Updating Ticket Descriptions
Always document your plan inside the ticket's Markdown file. Do not run interactive edit mode (which opens `$EDITOR`). Instead, pass the content directly or pipe it:
```bash
# Option A: Command-line string
ltk ticket edit b9-9b7d48 "## Requirements\n- Verify passwords using bcrypt\n- Return JWT token on success"

# Option B: Piped input
echo -e "## Requirements\n- Verify passwords using bcrypt\n- Return JWT token on success" | ltk ticket edit b9-9b7d48
```

### 5. Managing Status Updates
* **Blocked**: Tickets with unclosed dependencies are automatically marked `[blocked]`.
* **Open**: Tickets with no dependencies, or whose dependencies are all closed, are marked `[open]`.
* **In Progress**: To mark a ticket as being actively worked on, update the epic's `.tickets.json` file directly (under the ticket's `"status"` field, set it to `"in_progress"`).
* **Closed**: When a task is complete, run:
  ```bash
  ltk ticket close b9-9b7d48
  # This automatically unblocks b9-571801, transitioning its status from [blocked] to [open].
  ```

### 6. Troubleshooting Cycles
If you encounter a `circular dependency` error, run `ltk tree` to trace the path of dependencies, and use `ltk ticket delete` or rename/reconfigure dependencies to break the cycle.
