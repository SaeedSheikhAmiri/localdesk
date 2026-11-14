#!/bin/sh
# Scan staged agent skills with SkillSpector; static and local unless --llm is explicit.
set -eu
usage() {
	cat <<'EOF'
Usage: scripts/scan-skill.sh [--llm] [TARGET ...]

TARGET is a skill directory, SKILL.md, Git URL or zip archive. Defaults to skills/.
The scan is static (--no-llm) unless --llm is given; --llm sends skill contents to
the provider configured for SkillSpector. A .skillspector-baseline.yaml at the
repository root is applied when present. Any finding or incomplete coverage fails.
EOF
}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
llm=0
targets=""
for arg in "$@"; do
	case "$arg" in
		-h|--help) usage; exit 0 ;;
		--llm) llm=1 ;;
		-*) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
		*) targets="${targets}${arg}
" ;;
	esac
done
[ -n "$targets" ] || targets="skills
"
cli=${SKILLSPECTOR:-}
if [ -z "$cli" ] && [ -x "$root/.venv/bin/skillspector" ]; then cli="$root/.venv/bin/skillspector"; fi
if [ -z "$cli" ]; then cli=$(command -v skillspector 2>/dev/null || true); fi
if [ -z "$cli" ] || ! command -v "$cli" >/dev/null 2>&1; then
	printf '%s\n' 'SkillSpector is not installed. Install it with:' \
		'  uv tool install git+https://github.com/NVIDIA/skillspector.git' \
		'  python3.12 -m pip install "skillspector @ git+https://github.com/NVIDIA/skillspector.git"' >&2
	exit 2
fi
status=0
while IFS= read -r target; do
	[ -n "$target" ] || continue
	recursive=0
	if [ -d "$target" ]; then
		if ! find "$target" -type f \( -name SKILL.md -o -name skill.md \) -print -quit | grep -q .; then
			printf 'Skipping %s: no SKILL.md found.\n' "$target"
			continue
		fi
		if [ ! -f "$target/SKILL.md" ] && [ ! -f "$target/skill.md" ]; then recursive=1; fi
	fi
	set -- scan "$target" --format terminal
	if [ "$recursive" -eq 1 ]; then set -- "$@" --recursive; fi
	if [ "$llm" -eq 0 ]; then set -- "$@" --no-llm; fi
	if [ -f "$root/.skillspector-baseline.yaml" ]; then set -- "$@" --baseline "$root/.skillspector-baseline.yaml"; fi
	set -- "$@" --fail-on-findings --fail-on-incomplete
	if ! "$cli" "$@"; then status=1; fi
done <<EOF
$targets
EOF
exit "$status"
