# Update policy for coding agents

This policy keeps a clone current without interrupting production work or repeatedly changing the conversation state.

## When to check

Check for updates once when opening an existing clone in a new Codex, Claude Code, or Antigravity session. Check again only when at least 24 hours have passed, or immediately before a new production run that begins after that interval. Do not check during an active render, revision, native application test, or partially applied code change.

Run the check silently after the first session report when the clone is already current. Do not repeatedly tell the user that nothing changed.

## Safe check

1. Read the current commit, branch, and working-tree status.
2. If no `origin` remote exists, continue with the local build and report that automatic update checking is unavailable.
3. Fetch `origin/main` without modifying files.
4. Compare `HEAD` with `origin/main`.
5. If the clone is behind, summarize the available commits and ask the user whether to update now. If the user already asked for the latest build, that instruction is authorization to update.
6. If the working tree has changes, do not pull, stash, reset, discard, or overwrite them. Finish the authorized work, commit it, or ask how the user wants the changes preserved.

Use a fast-forward-only update:

```powershell
git fetch origin main
git status --short
git pull --ff-only origin main
python -m pip install -e ".[dev]" -c requirements-dev.lock
motion-engine version
python -m pytest
```

`git pull --ff-only` is idempotent. Running it again on the same commit leaves the clone unchanged. An update check must not create a new `runs/` project version, rewrite prompts, or repeat an already completed revision.

## After updating

Read the current `AGENTS.md`, `START_HERE.md`, `docs/desktop-agent-workflow.md`, and any release-specific documentation relevant to the request. Continue from the existing project files and current user intent. Do not restart the creative workflow or regenerate completed artifacts merely because code changed.

The repository build is visible near the top of `README.md`, `START_HERE.md`, and through:

```powershell
motion-engine version
```

If that command reports an older build after pulling, reinstall the editable package in the active Python environment before doing production work.

## Does the user need a new code session?

A normal fast-forward pull does not require a new chat or code session. Continue in the same conversation when the updated CLI starts normally and the current project artifacts still validate.

Tell the user to start a new code session only when at least one of these conditions applies:

- The coding tool loaded an installed skill or plugin whose files changed and the tool cannot reload it during the current session.
- A long-running Python, Node, preview, or Adobe helper process still holds the old code and cannot be restarted cleanly.
- The updated repository declares a breaking migration that changes the current project's MotionSpec or run format.
- The session has lost or contradicted the current project state after the update and rereading the maintained handoff cannot resolve it.

When a restart is required, say exactly why, identify the current project directory and latest completed artifact, and provide a continuation prompt. Never recommend a new session as a routine response to `git pull`.

