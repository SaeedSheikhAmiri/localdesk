# Maintainer approval and GitHub setup

This repository is a clean source preparation. Repository files alone **do not enable branch protection**. The initial release is prepared for the personal upstream repository; verify the live repository rules before claiming enforcement.

## Contribution model

Users fork, make a branch, and open a PR. Only maintainers receive write/admin access. Contributors do not get direct upstream push permission. Maintainers decide whether to merge and tag a release. Apache-2.0 still permits independent forks; upstream approval cannot restrict lawful downstream use.

Use at least one approval from a designated maintainer/code owner, successful CI, resolved review conversations, dismissal of stale reviews and approval of the latest push. Protect `main`; block force pushes/deletion, enforce for administrators, and avoid bypass lists. Turn off auto-merge. Prefer two maintainers so an author's own PR can receive independent review.

## Configure the real repository

1. Choose the GitHub owner/organization and repository name. Review the entire clean tree and audit result before uploading anything. Do not initialize Git in the original personal workspace or upload its history.
2. Start with this clean tree only; set the Git author identity intentionally (a suitable GitHub no-reply identity is an option). Do not upload a workstation `.app`, logs, generated runtime directories or real screenshots.
3. Create `.github/CODEOWNERS` from the example, naming actual maintainers who have write access; update `PUBLIC_FILES.json` after reviewing the change, then commit the file. Never publish a fake code-owner team or claim it enforces review when it does not exist.
4. In repository Settings → Rules/Branches, protect `main` with the controls above and require the **Quality (macOS)** status. The first CI run must finish before selecting its check by name.
5. Enable GitHub private vulnerability reporting, Dependabot alerts and push protection/secret scanning where available. Keep Actions workflow token permissions read-only and require approval for first-time outside contributors. Never use `pull_request_target` to execute fork code.
6. Verify the rule with an unapproved sample PR and a direct push attempt from a non-maintainer before announcing governance as active. Confirm a PR touching security/configuration requires code-owner review.
7. Publish an alpha release only after tests and the public audit pass. Include the source ZIP and its checksum. The app does not self-update or accept fork code automatically.

`python scripts/configure_github.py --repo OWNER/REPO --reviewer USERNAME` prints the proposed policy without writing to GitHub. After the actual CODEOWNERS file is committed and the check exists, the same command with `--apply` validates the remote CODEOWNERS and configures protection. It requires the user's own authorized `gh` login and repository administration permission. This preparation does not run it against any account.

References: [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
