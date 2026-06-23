# Before ANY Task — MANDATORY

Verify BEFORE your first edit/write in every task:

- [ ] In a worktree (`$PROJECT/.worktrees/<branch>`), NOT root checkout
- [ ] Read all applicable pre-read docs (see table below)
- [ ] `.tmp/` dir exists for command output storage

# Pre-Read Rules

Read linked doc BEFORE any work in that area. No exceptions.

| Area | Trigger | Doc |
|------|---------|-----|
| Shell | Using Bash tool | `~/.claude/docs/shell.md` |
| Git | commit, push, add, branch, merge, rebase, worktree, etc. | `~/.claude/docs/git-operations.md` |
| Go | Writing Go code | `~/.claude/docs/go.md` |
| Cmd output | Processing Bash output, git, curl, wget, kubectl, cloud CLIs | `~/.claude/docs/remote-data.md` |
| Commit msg | Formatting commit messages | `~/.claude/docs/commit-messages.md` |
| Debugging | Fixing complex/multi-component bugs | `~/.claude/docs/debugging.md` |
| Agent docs | Writing/editing CLAUDE.md, docs/, skills/ | `~/.claude/docs/agent-instructions.md` |
| Claude Code | Claude Code ONLY: task delegation, `/codex-exec`, slash-command workflows | `docs/claude-code.md` |

# GitHub

- ALWAYS use `github` CLI for GitHub interactions. NEVER scrape pages or construct API URLs manually.
- All `github` output → store to `.tmp/` first (see remote-data rules above).

# Execution

- Focus on solving root cause. Never skip tests unless user explicitly asks.
- Focus on implementation first. Minimize repeated tests, pass/fail counting, and other check-in work during active editing.
- Run broader verification only at meaningful checkpoints, before handoff, or when risk/blockers justify it.
- Ask before committing to git
- Prefer editing existing files over creating new ones
- Run tests after making changes
- Keep code simple — no over-engineering
- No unnecessary comments or docstrings

# Workflow

- When something goes sideways, stop and re-plan — don't keep pushing
- After finishing a task: run typecheck, tests, and lint before calling it done

# Style

- Prefer small, focused functions
- Use early returns over nested conditionals

# Reporting

- Final report: summary of work + worktree name (`.worktrees/<branch>`) or directory.

# Code Reviews

- Not-applicable review feedback → add inline code comment explaining why. Prevents repeat comments.
- Always build for amd64 and aarch64 (rpi5)
