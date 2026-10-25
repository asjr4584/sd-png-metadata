# GitHub Workflow Guardrails & Multi-Fork Synchronization

## End-to-End Session Summary
This document codifies the end-to-end operational rules, skills, and guardrails established during pull request management and fork synchronization across `gaijinworld/sd-png-metadata` and `asjr4584/sd-png-metadata`.

## Causes & Solutions for Encountered Issues

| # | Issue | Root Cause | Solution |
|---|---|---|---|
| 1 | Google OAuth Rejection | Direct Google OAuth (`accounts.google.com/v3/signin/rejected`) fails in remote automated browser sessions. | Use direct GitHub username/password authentication on `https://github.com/login`. |
| 2 | Disabled Issues Tab Pre-Merge Failure | Repositories with `has_issues: false` return HTTP `410 Gone` on `_list_issues`. | Handle HTTP 410 gracefully in `_list_issues` returning `count: 0, issues_disabled: True` so PR merges are not blocked. |
| 3 | Companion Fork Lag | Merging PRs into upstream `gaijinworld` leaves `asjr4584` companion fork behind. | Execute automated `sync_fork` (`POST /repos/{fork_owner}/{repo}/merge-upstream` or `gh repo sync`) immediately after every upstream merge. |
| 4 | Unverified Branch Divergence | Pushing directly without checking branch status can cause lost commits or push rejections. | Perform pre-push divergence checks (`compare/main...<branch>`) before pushing or creating PRs. |
| 5 | Unsafe PR Merge Attempt | Merging without checking conflict status leads to merge failures or broken builds. | Run `check_pr` to verify `mergeable != False` and ensure open issues/conflicts are resolved prior to calling `merge_pr`. |
| 6 | Branch Ref Staleness (Compare-And-Swap) | Concurrent branch updates lead to non-fast-forward states. | Verify head commit SHA before executing merges or fast-forwards (CAS verification). |
| 7 | Non-Standard Default Branch Assumptions | Assuming `main` vs `master` as default branch across different repos. | Explicitly inspect repository default branch (`master` for `sd-png-metadata`, `main` for `rea`). |

## Updated Skills Summary
- **`check_pr`**: Inspects PR state, `mergeable`, `mergeable_state`, head SHA, and diff counts via `GET /repos/{owner}/{repo}/pulls/{pull_number}`.
- **`merge_pr`**: Enforces pre-merge open-issue check (`list_issues` with `state="open"`) and merge-conflict gate (`mergeable != False`) before calling `PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge`.
- **`sync_fork`**: Calls `POST /repos/{fork_owner}/{repo}/merge-upstream` (or `gh repo sync asjr4584/{repo} --branch {default_branch}`) immediately after upstream merge so companion forks stay updated.
- **HTTP 410 Disabled-Issues Handling**: Catches HTTP 410 Gone when fetching issues for repos with disabled Issues tabs, treating it as 0 open issues (`issues_disabled: True`).

## Multi-Fork Synchronization & Remote Browser Rules
1. **Multi-Fork Sync Protocol**: Whenever a PR is merged on `gaijinworld/sd-png-metadata:master` or `gaijinworld/rea:main`, immediately sync `asjr4584/sd-png-metadata` or `asjr4584/rea` via GitHub Web Interface "Sync fork" -> "Update branch" or the `merge-upstream` API endpoint.
2. **Remote-Browser Sign-In Rule**: Authenticate directly using GitHub username and password on `https://github.com/login`. Avoid Google OAuth flows (`accounts.google.com/v3/signin/rejected`).
3. **Local CLI Environment**: Local working directory for `sd-png-metadata` is `C:\src\sd-png-metadata` on branch `master`.
