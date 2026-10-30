# Security policy and boundaries

This alpha is a single-user, loopback-only macOS application. Do not deploy it as a multi-user web service. No security certification or immunity to prompt injection is claimed.

## Controls

- Separate installation-local credentials, signed HttpOnly/SameSite sessions, expiring one-use login tickets, CSRF/origin/host checks, CSP and bounded requests.
- Separate engine HOME/XDG directories; existing personal OpenCode credentials, history and profiles are not imported.
- macOS policies are generated for the current installation. Document parsing has no network or file-write permission. Task writes are limited to its workspace and selected engine runtime directories; source, app secrets and task configuration are excluded.
- The launcher verifies listeners before reusing services or sending credentials and fails closed when the protection mechanism is unavailable.
- Tool policy requires web and shell approvals. Read-only agent profiles deny file edits and shell/task delegation.
- Model downloads, online model use, source imports, and permanent cleanup are explicit user choices.

## Known limitations

OpenCode 1.19.4's legacy permission-list response can fail if a webfetch request omits optional metadata such as timeout. A malformed pending request can affect the list for other sessions. LocalDesk supplies compatibility guidance to the model and displays a safe error with Stop available. Guidance is not a guaranteed upstream fix. Never disable approvals to work around it. Stop the affected task; if restarting the engine is necessary, first finish/stop your own other tasks.

Approved shell commands are powerful. A shell can access the task engine's environment, including an online provider key when online mode is selected. Do not approve commands that print secrets, upload private files, install persistence, or alter protection. Confinement is not a full VM and cannot protect against compromised system software or an administrator.

Conversation data is stored with owner-only filesystem permissions, without application-level encryption. Browser storage holds a backup. Treat browser extensions, backups and your OS account accordingly. Strict source mode is extractive; the normal LLM-with-sources mode is not guaranteed to remain grounded. No automatic model-weight training occurs.

## Reporting

Do not open a public issue containing credentials, personal data or a working exploit against another user's system. After the repository is hosted, use GitHub's private vulnerability reporting if maintainers enable it. Until a private channel exists, do not transmit sensitive details; publish only a non-sensitive request for a private channel. Maintainers must configure this before announcing the release (see GOVERNANCE).

Alpha support: only the latest reviewed alpha is supported. Security fixes require maintainer review and a new release; forks do not automatically update installed applications.
