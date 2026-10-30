# Source distribution privacy

The release is assembled from `PUBLIC_FILES.json`, not a recursive copy of a development workstation. The builder rejects symlinks, unreviewed files and an output path inside the source tree. ZIP timestamps and permissions are deterministic; Git metadata, caches and generated binaries are excluded.

The public-content check rejects runtime databases/logs, real agent/account files, private-key/provider-token patterns, absolute workstation identities, email addresses, font payloads and unexpected binaries. A local-only `--private-origin` option can additionally compare exact secret/profile values without printing them or writing an origin path into the public report. Pattern scanning has false negatives; manual review and a fresh initial repository remain necessary.

This source preview distributes no commercial font, existing conversation, personal screenshot, model weight, engine binary or provider key. The included tests and preset examples are synthetic/generic. Each user gets empty local data and a newly generated password. Online model use requires their own explicit configuration.

Application data is outside the source checkout. Copying or uploading that data directory later is not made safe by this source release process. Check every future PR and release; a clean initial archive does not guarantee future commits remain clean.
