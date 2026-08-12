#!/usr/bin/env bash

set -euo pipefail

readonly SCANNER_SHA='1a269c9c77f9291880dd90c2e154fb2185978a3a'
readonly SCANNER_LOCK_SHA256='d1b010e10f4269745c1e89dd80fbb03d0d1e0948d3a0348af3b5421924de3570'
readonly RULES=(
  CMD_EXEC
  CODE_INJECT
  PWN_REQUEST
  REPOJACKABLE
  UNPINNED_ACTION
  UNSAFE_INPUT_ASSIGN
  WORKFLOW_RUN
)

scanner_fail() {
  printf 'github-actions-scanner: %s\n' "$1" >&2
  exit 1
}

[[ $# == 8 ]] || scanner_fail 'expected repository identity and event trust fields'
owner=$1
repository=$2
commit_sha=$3
event_name=$4
actor=$5
head_repository=$6
pull_request_user=$7
author_association=$8

scanner_token=${GITHUB_TOKEN-}
unset GITHUB_TOKEN GH_TOKEN ZIZMOR_GITHUB_TOKEN MISE_GITHUB_TOKEN APP_TOKEN
unset GOPRIVATE GONOSUMDB GONOPROXY
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_NOSYSTEM=1

[[ ${#owner} -le 39 && $owner =~ ^[A-Za-z0-9-]+$ && $owner != -* && $owner != *- ]] ||
  scanner_fail 'invalid repository owner'
[[ ${#repository} -le 100 && $repository =~ ^[A-Za-z0-9_.-]+$ ]] ||
  scanner_fail 'invalid repository name'
[[ $repository != . && $repository != .. ]] || scanner_fail 'invalid repository name'
[[ $commit_sha =~ ^[0-9a-f]{40}$ ]] || scanner_fail 'commit SHA must be exactly 40 lowercase hex characters'

runner_temp=${RUNNER_TEMP-}
workspace=${GITHUB_WORKSPACE-}
for root_name in runner_temp workspace; do
  root=${!root_name}
  [[ -n $root && $root == /* && $root != / && $root != *$'\n'* && $root != *$'\r'* ]] ||
    scanner_fail "$root_name must be a non-root absolute single-line path"
  case "/${root#/}/" in
    */../* | */./*) scanner_fail "$root_name contains a dot path segment" ;;
  esac
done

runner_temp=${runner_temp%/}
workspace=${workspace%/}
results_root="$runner_temp/github-actions-scanner-results"
npm_cache="$runner_temp/github-actions-scanner-npm-cache"
state_file="$runner_temp/github-actions-scanner-state.tsv"
scanner_source="$workspace/github-actions-scanner-source"
scan_url="https://github.com/$owner/$repository/commit/$commit_sha"

[[ $results_root == "$runner_temp/github-actions-scanner-results" ]] ||
  scanner_fail 'result path escaped RUNNER_TEMP'
[[ $npm_cache == "$runner_temp/github-actions-scanner-npm-cache" ]] ||
  scanner_fail 'npm cache path escaped RUNNER_TEMP'
[[ $state_file == "$runner_temp/github-actions-scanner-state.tsv" ]] ||
  scanner_fail 'state path escaped RUNNER_TEMP'
[[ $scanner_source == "$workspace/github-actions-scanner-source" ]] ||
  scanner_fail 'scanner source path escaped GITHUB_WORKSPACE'

safe_directory() {
  local path=$1
  [[ ! -L $path ]] || return 1
  [[ ! -e $path || -d $path ]] || return 1
}

safe_directory "$results_root" || scanner_fail 'result path is stale, symlinked, or non-directory'
safe_directory "$npm_cache" || scanner_fail 'npm cache path is symlinked or non-directory'
[[ ! -L $state_file && ! -e $state_file ]] || scanner_fail 'state path is stale or symlinked'

states=(incomplete incomplete incomplete incomplete incomplete incomplete incomplete)
counts=(0 0 0 0 0 0 0)

cleanup() {
  local status=$? cleanup_failed=0 path index
  trap - EXIT

  scanner_token=
  unset scanner_token

  if [[ -L $state_file || (-e $state_file && ! -f $state_file) ]]; then
    cleanup_failed=1
  else
    umask 077
    : >"$state_file" || cleanup_failed=1
    chmod 600 "$state_file" || cleanup_failed=1
    if ((cleanup_failed == 0)); then
      for index in "${!RULES[@]}"; do
        printf '%s\t%s\t%d\n' "${RULES[$index]}" "${states[$index]}" "${counts[$index]}" >>"$state_file" ||
          cleanup_failed=1
      done
    fi
  fi

  for path in "$results_root" "$npm_cache"; do
    if safe_directory "$path"; then
      rm -rf -- "$path" || cleanup_failed=1
    else
      cleanup_failed=1
    fi
  done

  for index in "${!RULES[@]}"; do
    printf '%s: %s (%d)\n' "${RULES[$index]}" "${states[$index]}" "${counts[$index]}"
  done

  if ((cleanup_failed != 0 && status == 0)); then
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

eligible=false
if [[ $actor != 'dependabot[bot]' ]]; then
  case $event_name in
    push | workflow_dispatch)
      eligible=true
      ;;
    pull_request)
      if [[ $head_repository == "$owner/$repository" &&
        $pull_request_user != 'dependabot[bot]' ]]; then
        case $author_association in
          OWNER | MEMBER | COLLABORATOR) eligible=true ;;
        esac
      fi
      ;;
  esac
fi

if [[ $eligible != true ]]; then
  scanner_token=
  unset scanner_token
  exit 0
fi
if [[ -z $scanner_token ]]; then
  scanner_token=
  unset scanner_token
  exit 0
fi

[[ -d $scanner_source && ! -L $scanner_source ]] ||
  scanner_fail 'scanner source must be a regular directory'
[[ -f $scanner_source/index.mjs && ! -L $scanner_source/index.mjs ]] ||
  scanner_fail 'scanner entry point must be a regular file'
[[ -f $scanner_source/package-lock.json && ! -L $scanner_source/package-lock.json ]] ||
  scanner_fail 'scanner lockfile must be a regular file'
source_sha=$(git -C "$scanner_source" rev-parse HEAD)
[[ $source_sha == "$SCANNER_SHA" ]] || scanner_fail 'scanner source SHA mismatch'
lock_digest=$(shasum -a 256 "$scanner_source/package-lock.json")
lock_digest=${lock_digest%% *}
[[ $lock_digest == "$SCANNER_LOCK_SHA256" ]] || scanner_fail 'scanner lockfile digest mismatch'

rm -rf -- "$results_root"
umask 077
mkdir -p -- "$results_root"
chmod 700 "$results_root"

for index in "${!RULES[@]}"; do
  rule=${RULES[$index]}
  output="$results_root/$rule.json"
  log="$results_root/$rule.log"
  [[ ! -e $output && ! -L $output && ! -e $log && ! -L $log ]] ||
    scanner_fail 'per-rule result path was not fresh'

  scanner_status=0
  GITHUB_TOKEN=$scanner_token node "$scanner_source/index.mjs" \
    --env /dev/null \
    --scan-rules "$rule" \
    --output "$output" \
    --format json \
    scan-repo --url "$scan_url" >"$log" 2>&1 || scanner_status=$?

  state=incomplete
  count=0
  if ((scanner_status == 0)) &&
    [[ -f $output && ! -L $output && -f $log && ! -L $log ]] &&
    ! grep -Eiq \
      '(^|[[:space:]])(warn|error):|::(warning|error)::|failed to (scan|get repo|get tarball)|rate.?limit|network|ECONN|ENOTFOUND|ETIMEDOUT|EAI_AGAIN|socket hang up|non 200 response|max size exceeded|getFilesFromArchive STUCK|RequestError|HttpError' \
      "$log" &&
    ! LC_ALL=C grep -q $'\033' "$log" &&
    ! LC_ALL=C grep -q $'\r' "$log" &&
    jq -e --arg rule "$rule" \
      'type == "array" and all(.[]; (.rule.id? == $rule))' "$output" >/dev/null 2>&1; then
    count=$(jq -r 'length' "$output")
    if ((count > 0)); then
      state=findings
    else
      state=clean
    fi
  fi
  states[$index]=$state
  counts[$index]=$count
done
