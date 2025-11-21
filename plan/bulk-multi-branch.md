# Merge plan: `romanz/bulk-multi-branch`

Goal
----
Create a single multi-feature branch called `romanz/bulk-multi-branch` that combines changes from:

- `origin/copilot/add-es-bulk-loader-script`
- `origin/copilot/update-load-fit-to-es-config`
- local snapshot branch `romanz/snapshot211125` (contains local tracked changes)

High-level approach
-------------------
1. Create a new branch from `origin/main` named `romanz/bulk-multi-branch`.
2. Merge each feature branch into it one by one (`add-es-bulk-loader-script`, `update-load-fit-to-es-config`, `romanz/snapshot211125`).
3. Resolve conflicts with small, focused commits and run tests after each merge.
4. When all merges are clean and tests pass, push `romanz/bulk-multi-branch` to `origin` and open a PR for final review.

Detailed steps & commands
------------------------

1) Make sure your local `main` is up to date:

```sh
git fetch origin
git checkout main
git pull --ff-only origin main
```

2) Create the combined branch from `main`:

```sh
git checkout -b romanz/bulk-multi-branch
```

3) Merge the first remote feature branch and resolve conflicts if any:

```sh
git merge --no-ff origin/copilot/add-es-bulk-loader-script
# fix conflicts in editor, then
git add <files-fixed>
git commit
# run quick tests (see checklist below)
```

4) Merge the second remote feature branch:

```sh
git merge --no-ff origin/copilot/update-load-fit-to-es-config
# resolve conflicts, commit, run tests
```

5) Merge the local snapshot branch (if present locally):

```sh
git merge --no-ff romanz/snapshot211125
# resolve conflicts, commit, run tests
```

Notes on conflict resolution
---------------------------
- Prefer small, targeted conflict resolutions: keep behavior from the branch with better tests or clearer intent.
- If a conflict affects binary files (e.g., `.fit`), avoid committing large binaries into the combined branch — prefer keeping only code and small metadata. If you must keep a binary, consider storing it externally (S3) or in a release artifact.
- Run `git mergetool` if you prefer a GUI to resolve text conflicts.

Testing checklist (quick smoke tests)
-----------------------------------
- Run `python load_fit_to_es.py --help` if present to ensure CLI loads.
- Run any small unit or script-level checks you have (e.g., `python parse_apple_hr.py` dry-run).
- Verify there are no unintended deletions of repository files (check `git status` and `git diff --staged`).

Push and PR
-----------
When happy with the merged branch:

```sh
git push origin romanz/bulk-multi-branch
# then open a PR from romanz/bulk-multi-branch -> main in GitHub
```

If you want a remote snapshot saved before merging (recommended), push the local snapshot branch:

```sh
git push origin romanz/snapshot211125
```

Auth note
---------
Pushing may require a GitHub auth method (PAT or SSH). If `git push` fails with authentication errors, either configure SSH remotes or set a personal access token (PAT) as your credential helper.

Follow-ups
----------
- After opening the PR, run CI (if available) and iterate on any requested fixes.
- When PR is approved, choose a merge strategy (squash/merge or merge commit) and merge into `main`.

---
Generated: snapshot/plan created 2025-11-21
