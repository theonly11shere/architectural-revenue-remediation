# V7.8.1 merge resolution

Engine: `v7.8.1-universal-path-refinement`; API: `7.8.1`.
Reviewed incoming commit: `6520589cc22c5c194602472727c979e25f2f7bf4`.

The supplied review ZIP contains local committed versions, incoming committed
versions, conflicted working files, the incoming diff, manifest and Git status.
The incoming backend identifies itself as V7.7.1. Its relevant backend changes
are already included in your validated V7.8.1 compatibility release.

| File | Resolution |
| --- | --- |
| hybrid_scanner.py | Keep the V7.8.1 engine version and evidence collection. |
| main.py | Keep the V7.8.1 API fallback and existing access/public-report changes. |
| pathway_markers.py | Keep the V7.8.1 receipt-to-marker bridge, stage evidence and outcome checks. |
| report_engine.py | Keep the V7.8.1 report label and existing TCEA report changes. |

The four resolved files retain the content outside the conflicts. The resulting
files match your committed V7.8.1 files after line-ending normalization. The
cleanly merged architect_review.py matches too, so no replacement is needed.
The incoming diff's changes to commercial_contracts.py,
scan_execution_protocol.py and scorer.py are present in the compatibility
release used for validation. The verifier checks those files in your checkout.

Git checked out the uploaded committed files using Windows CRLF endings,
while the original manifest hashes used LF. The updated verifier accepts that
line-ending conversion without accepting genuine source changes. Two new
regression cases verify both behaviors. The scanner engine stays at V7.8.1.

## Install and finish the pending merge

1. Open this ZIP and copy its ten files into your existing backend folder,
   beside `main.py`, replacing matching files. Do not delete the rest of the
   backend. This overlay requires the V7.8.1 Compatibility Repair already there.
2. In PowerShell, run:

```powershell
Set-Location 'C:\Users\curti\Downloads\trilloka_scanner'
.\.venv-curti\Scripts\python.exe verify_v781.py
```

Continue only after all 650 tests pass. If verification lists changed files,
keep the output and inspect those differences; do not bypass verification.

3. Stage these ten files only:

```powershell
$mergeFiles = @(
    'hybrid_scanner.py'
    'main.py'
    'pathway_markers.py'
    'report_engine.py'
    'verify_v781.py'
    'test_v781_refinements.py'
    'RELEASE_MANIFEST.json'
    'START_HERE.md'
    'VALIDATION_RESULTS.txt'
    'MERGE_NOTES.md'
)
git add -- $mergeFiles
git diff --name-only --diff-filter=U
git diff --cached --stat
git diff --cached -- index.html disclaimer.html
```

The unresolved-file command must print nothing. The supplied status also shows
`index.html` modified and `disclaimer.html` deleted in the index. Their contents
were not supplied or reviewed. Inspect the displayed frontend diff and confirm
those changes are intended before committing. This ZIP does not alter them.
Avoid `git add .`: the status includes an untracked learning database and
unrelated files. Previously staged files will also be part of the merge commit.

4. Complete the pending merge, then push after the commit succeeds:

```powershell
git commit --no-edit
```

```powershell
git push -u origin main
git status
```

If a command fails, stop and keep its output before proceeding. Do not force
push, reset the branch, select an entire side blindly, or start another pull
while this merge is pending. If the remote advances again, keep the new push
rejection output so that later changes can be reviewed separately.

## Saved changes from the earlier pull

The pull mentioned stashed changes. After completing the merge, inspect:

```powershell
git stash list
```

Do not blindly pop the first entry. If an entry is the autostash from this pull,
inspect that specific entry using `git stash show --stat 'stash@{N}'`, replacing
N with its actual number. Restore it only if its edits are still needed using
`git stash apply 'stash@{N}'`. Apply keeps the saved copy. Resolve any conflicts
and rerun verification if restored edits touch release files. If the autostash
was already restored by Git, do not apply it again. Keep saved entries until
you have confirmed the relevant edits are present.

This package was prepared offline. You perform the local Git steps, login if
your Git client requires it, and deployment yourself.
