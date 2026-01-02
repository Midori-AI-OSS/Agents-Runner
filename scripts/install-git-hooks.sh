#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

git config core.hooksPath .githooks

if [ ! -f .githooks/pre-commit ]; then
  echo "Missing .githooks/pre-commit; did you forget to check it into the repo?" >&2
  exit 1
fi

chmod +x .githooks/pre-commit

if [ -d .git/hooks ]; then
  cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
exec "${repo_root}/.githooks/pre-commit"
HOOK
  chmod +x .git/hooks/pre-commit
fi

echo "Installed git hooks via core.hooksPath=.githooks"
