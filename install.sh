#!/usr/bin/env bash
# Copy the orchestrator setup into a project's .claude/ folder.
# Usage: ./install.sh [target-project-dir] [--force]
# Existing files are kept unless --force is given; then run /orchestrator-init in Claude Code there.
# The project's own data (orchestrator/profile.md, orchestrator/ledger.md) is never overwritten.
set -euo pipefail

src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/template/.claude"
target="."
force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) target="$arg" ;;
  esac
done

target="$(cd "$target" && pwd)"
if ! git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "warning: $target is not a git repository; /execute-plan needs git worktrees." >&2
fi

copied=0; kept=0
while IFS= read -r -d '' file; do
  rel="${file#"$src"/}"
  dest="$target/.claude/$rel"
  data=0
  [[ "$rel" == orchestrator/profile.md || "$rel" == orchestrator/ledger.md ]] && data=1
  if [[ -e "$dest" && ( $data -eq 1 || $force -eq 0 ) ]]; then
    if [[ $data -eq 1 ]]; then
      echo "kept     .claude/$rel (project data, never overwritten)"
    else
      echo "kept     .claude/$rel (exists; --force overwrites)"
    fi
    kept=$((kept + 1))
    continue
  fi
  mkdir -p "$(dirname "$dest")"
  cp "$file" "$dest"
  copied=$((copied + 1))
done < <(find "$src" -type f -not -name '*.pyc' -print0)

echo
echo "Copied $copied files into $target/.claude ($kept kept)."
echo "Next: open Claude Code in $target and run  /orchestrator-init"
