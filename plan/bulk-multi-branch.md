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

Preserving local `garmin/` files
--------------------------------
You mentioned you want to avoid moving your local `garmin/` folder between branches. Two safe approaches are provided below; the first is recommended because it keeps your working copy untouched while you perform merges in an isolated workspace.

Option A — Recommended: use a separate worktree and sparse-checkout (no changes to your current working tree)

```sh
# create an isolated worktree from origin/main (outside current working tree)
git fetch origin
git worktree add ../fit-merge origin/main
cd ../fit-merge

# enable sparse-checkout and exclude the garmin folder so it is not present in this worktree
git sparse-checkout init --sparse
git sparse-checkout set '/*' '!/garmin'

# create the combined branch and perform merges here
git checkout -b romanz/bulk-multi-branch
git merge --no-ff origin/copilot/add-es-bulk-loader-script
git merge --no-ff origin/copilot/update-load-fit-to-es-config
git merge --no-ff romanz/snapshot211125

# resolve conflicts and test in this isolated worktree, then push
git push origin romanz/bulk-multi-branch
```

Notes: this keeps your original working tree (and its `garmin/` files) untouched. The worktree will not have `garmin/` checked out, so merges won't attempt to move or delete those files locally.

Option B — Merge on your main working copy but keep local `garmin/` files (restore after merge)

If you prefer to do merges in-place, you can tell Git to keep your local `garmin/` contents after a merge. This is slightly more manual but works when patches only modify code and metadata:

```sh
git checkout -b romanz/bulk-multi-branch
git merge --no-ff origin/copilot/add-es-bulk-loader-script || true
# if merge succeeds or after resolving textual conflicts, ensure garmin stays as-is:
git checkout --ours -- garmin || true
git add garmin && git commit --no-edit || true

git merge --no-ff origin/copilot/update-load-fit-to-es-config || true
git checkout --ours -- garmin || true
git add garmin && git commit --no-edit || true

git merge --no-ff romanz/snapshot211125 || true
git checkout --ours -- garmin || true
git add garmin && git commit --no-edit || true

# run tests, then push
git push origin romanz/bulk-multi-branch
```

Notes: `git checkout --ours -- garmin` restores the `garmin/` tree from the current branch in case the merge attempted to change or delete it. Use this only when you are confident the `garmin/` contents should remain exactly as in your working copy.


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
