# Merge plan (concise)

Goal
- Combine these branches into one multi-feature branch while preserving your local `garmin/` data:
	- `origin/copilot/add-es-bulk-loader-script`
	- `origin/copilot/update-load-fit-to-es-config`
	- `romanz/snapshot211125`

Best recommendation
- Use a separate worktree + sparse-checkout that excludes `garmin/`. Do all merges there, run tests, then push the combined branch. This keeps your main working tree and local `.fit` files untouched.

Quick steps
1) Create isolated worktree and exclude `garmin/`:

```sh
git fetch origin
git worktree add ../fit-merge origin/main
cd ../fit-merge
git sparse-checkout init --sparse
git sparse-checkout set '/*' '!/garmin'
```

2) Create combined branch and merge in order:

```sh
git checkout -b romanz/bulk-multi-branch
git merge --no-ff origin/copilot/add-es-bulk-loader-script
git merge --no-ff origin/copilot/update-load-fit-to-es-config
git merge --no-ff romanz/snapshot211125
# resolve conflicts, run quick tests
```

3) Push and open PR:

```sh
git push origin romanz/bulk-multi-branch
# open PR -> main on GitHub
```

If you later merge the combined branch into your local `main` but must keep local `garmin/` intact, do a controlled merge and restore `garmin/` if needed:

```sh
# in your original repo working tree
git fetch origin
git checkout main
git merge origin/romanz/bulk-multi-branch || true
git checkout --ours -- garmin || true
git add garmin && git commit --no-edit || true
```

Notes
- This avoids moving or deleting local `.fit` files during merging.
- Consider moving large binaries out of the repo (Git LFS or external storage) to simplify future merges.
- The concise plan is committed to `plan/bulk-multi-branch.md` on `romanz/snapshot211125`.

Auth: pushing requires SSH or a PAT.

