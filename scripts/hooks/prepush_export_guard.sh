#!/usr/bin/env bash
# scripts/hooks/prepush_export_guard.sh — pre-push guard (eksport-sanktsii)
# MOSTY:
# - (Yavnyy) Blokiruet push na GitHub, esli v kommite est zapreschennye puti.
# - (Skrytyy #1) Belyy spisok isklyucheniy iz config/export_whitelist.txt.
# - (Skrytyy #2) Pereklyuchatel ALLOW_PUBLIC_SYNERGY_PUSH=1 dlya osoznannoy publikatsii.
# ZEMNOY ABZATs:
# Deshevyy i nadezhnyy barer ot sluchaynogo vykladyvaniya zakrytykh moduley v publichnyy repozitoriy. c=a+b
set -euo pipefail

REMOTE_NAME="${1:-origin}"
REMOTE_URL="${2:-${REMOTE_NAME}}"

# Esli yavno razresheno — vykhodim
if [[ "${ALLOW_PUBLIC_SYNERGY_PUSH:-0}" == "1" ]]; then
  exit 0
fi

# Srabatyvaem tolko dlya GitHub (imitatsiya privat/pablik cherez URL)
if ! grep -qiE 'github\.com' <<< "$REMOTE_URL"; then
  exit 0
fi

# Schityvaem pary refs so stdin: <local_ref> <local_sha> <remote_ref> <remote_sha>
changed_files=()
while read -r local_ref local_sha remote_ref remote_sha; do
  if [[ -z "${local_sha:-}" || -z "${remote_sha:-}" ]]; then
    continue
  fi
  if [[ "$remote_sha" == "0000000000000000000000000000000000000000" ]]; then
    # novyy branch — vozmem vse fayly kommita
    mapfile -t files < <(git show --pretty="" --name-only "$local_sha")
  else
    mapfile -t files < <(git diff --name-only "$remote_sha" "$local_sha")
  fi
  changed_files+=("${files[@]}")
done

# Unikaliziruem
mapfile -t changed_files < <(printf "%s\n" "${changed_files[@]:-}" | grep -v '^$' | sort -u)

# Esli net izmeneniy — vykhodim
if [[ "${#changed_files[@]}" -eq 0 ]]; then
  exit 0
fi

# Patterny blok-lista
deny_regex='^(modules/synergy/|selfupgrade/|garage/|windows/|keys/|scripts/.+internal.+)'

# Belyy spisok (patterny grep -E, odin na stroku)
WHITELIST_FILE="${EXPORT_GUARD_WHITELIST:-config/export_whitelist.txt}"
whitelist_patterns=""
if [[ -f "$WHITELIST_FILE" ]]; then
  whitelist_patterns="$(grep -vE '^\s*(#|$)' "$WHITELIST_FILE" || true)"
fi

violations=()
for f in "${changed_files[@]}"; do
  if [[ "$f" =~ $deny_regex ]]; then
    skip=0
    # whitelist?
    if [[ -n "$whitelist_patterns" ]]; then
      while IFS= read -r pat; do
        if [[ "$f" =~ $pat ]]; then
          skip=1
          break
        fi
      done <<< "$whitelist_patterns"
    fi
    if [[ "$skip" -eq 0 ]]; then
      violations+=("$f")
    fi
  fi
done

if [[ "${#violations[@]}" -gt 0 ]]; then
  echo "✖ Export guard: zapreschennye puti dlya publichnogo GitHub:" >&2
  printf '  - %s\n' "${violations[@]}" >&2
  echo >&2
  echo "Esli eto osoznannaya publikatsiya — ustanovite ALLOW_PUBLIC_SYNERGY_PUSH=1 pered pushem" >&2
  echo "Ili dobavte konkretnye fayly v belyy spisok: config/export_whitelist.txt" >&2
  exit 1
fi

exit 0
