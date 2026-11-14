# Skills

Optional third-party agent skills staged for review. LocalDesk never executes them.

- One directory per skill, containing `SKILL.md`.
- No credentials, runtime data, model weights or generated reports.
- Scan before use: `sh scripts/scan-skill.sh` scans this directory with a static,
  local-only SkillSpector pass. Add `--llm` only when you deliberately want skill
  contents sent to the provider configured for SkillSpector.
- CI runs the same static scan whenever anything under `skills/` changes.
- A `SAFE` verdict is a heuristic, not proof. Persian and image-based content can
  evade pattern matching.
- Every file added here must also be listed in `PUBLIC_FILES.json`; release builds
  reject a tree that differs from that allowlist.
