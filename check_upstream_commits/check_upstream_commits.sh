#!/bin/bash
#set -x
set -e

usage() {
    echo "Usage: $0 [-b branch] [-u upstream/branch] [-q] <sha_list_file>"
    echo "  -b branch         Branch to check (default: current branch)"
    echo "  -u upstream/branch  Upstream remote/branch (default: upstream/master)"
    echo "  -q                Quiet mode (only summary)"
    exit 1
}

BRANCH=""
UPSTREAM="upstream/master"
QUIET=0

# Support for -h and --help
for arg in "$@"; do
    if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
        usage
    fi
done

while getopts "b:u:q" opt; do
    case $opt in
        b) BRANCH="$OPTARG" ;;
        u) UPSTREAM="$OPTARG" ;;
        q) QUIET=1 ;;
        *) usage ;;
    esac
done
shift $((OPTIND-1))

if [ $# -ne 1 ]; then
    usage
fi

SHA_LIST_FILE="$1"
if [ ! -f "$SHA_LIST_FILE" ]; then
    echo "File not found: $SHA_LIST_FILE"
    exit 1
fi

# Check for Linux git repo in current directory or via LINUX_GIT
check_linux_repo() {
    local repo_dir="$1"
    if [ -d "$repo_dir/.git" ]; then
        return 0
    else
        return 1
    fi
}

if ! check_linux_repo "."; then
    if [ -z "$LINUX_GIT" ] || ! check_linux_repo "$LINUX_GIT"; then
        echo "Error: Not in a Linux git repo and LINUX_GIT is not set to a valid Linux git repo." >&2
        exit 1
    else
        cd "$LINUX_GIT"
    fi
fi

if [ -z "$BRANCH" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
fi

PRESENT=0
REVIEW=0
MISSING=0
TOTAL=0
NOTUPSTREAM=0

output() {
    if [ $QUIET -eq 0 ]; then
        echo "$@"
    fi
}

# Check for 'upstream' remote if UPSTREAM is default and not specified by user
if [ "$UPSTREAM" = "upstream/master" ]; then
    if ! git remote | grep -qx 'upstream'; then
        echo "Remote branch containing upstream Linux kernel source was not found. Please specify the upstream remote branch with the -u parameter." >&2
        echo "" >&2
        echo "Alternatively, you can add and populate the remote with the following:" >&2
        echo "" >&2
        echo "    git remote add upstream https://github.com/torvalds/linux.git" >&2
        echo "    git fetch upstream" >&2
        exit 1
    fi
fi

while IFS= read -r line; do
    # Skip lines that are only whitespace or comments
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    SHA=$(echo "$line" | awk '{print $1}')
    TOTAL=$((TOTAL+1))
    STATUS=""
    ABBREV="------------"

    # 1. Check if SHA is present in branch
    if git merge-base --is-ancestor "$SHA" "$BRANCH" 2>/dev/null; then
        # Get abbreviated SHA from local branch
        ABBREV=$(git rev-parse --short=12 "$SHA")
        output "$(printf "%-7s (%-8s) %s" "EXISTS" "$ABBREV" "$line")"
        EXISTS=$((EXISTS+1))
        continue
    fi

    # 2. Check if SHA is reachable from upstream branch and get title
    if ! git merge-base --is-ancestor "$SHA" "$UPSTREAM" 2>/dev/null; then
        output "$(printf "%-7s (%-8s) %s" "BADSHA" "$ABBREV" "$line")"
        BADSHA=$((BADSHA+1))
        continue
    fi
    TITLE=$(git log --format=%s -n 1 "$SHA")

    # 3. Search for similar title in branch (ignore tags/prefixes)
    # Remove tags/prefixes from title for search
    TITLE_BASENAME=$(echo "$TITLE" | sed 's/^[^:]*: *//')
    MATCH_FOUND=0
    while read -r commit_hash commit_title; do
        commit_title_basename=$(echo "$commit_title" | sed 's/^[^:]*: *//')
        if [[ "$commit_title_basename" == *"$TITLE_BASENAME"* ]]; then
            # Check for cherry-pick/backport/upstream note:
            #
            #    Cherry-picked from commit: $SHA
            #    Cherry picked from commit: $SHA
            #    Backported from commit: $SHA
            #    commit $SHA upstream
            #    Upstream commit $SHA
	    #
            if git log -1 --format=%B "$commit_hash" | grep -qi -E "Cherry[- ]picked from commit:?\s*$SHA|Backported from commit:?\s*$SHA|commit\s+$SHA[0-9a-f]*\s+upstream|Upstream commit\s+$SHA"; then
                # Compare diffs
                ABBREV_LOCAL=$(git rev-parse --short=12 "$commit_hash")
                if diff -u -w \
                    <(git show --format= "$SHA" | grep -E '^[+-][^+-]') \
                    <(git show --format= "$commit_hash" | grep -E '^[+-][^+-]') \
                    >/dev/null; then
                    output "$(printf "%-7s (%-8s) %s" "EXISTS" "$ABBREV_LOCAL" "$line")"
                    EXISTS=$((EXISTS+1))
                else
                    output "$(printf "%-7s (%-8s) %s" "REVIEW" "$ABBREV_LOCAL" "$line")"
                    REVIEW=$((REVIEW+1))
                fi
                MATCH_FOUND=1
                break
            fi
        fi
    done < <(git log "$BRANCH" --format='%H %s' --grep="$TITLE_BASENAME" --fixed-strings)
    if [ $MATCH_FOUND -eq 0 ]; then
        output "$(printf "%-7s (%-8s) %s" "ABSENT" "$ABBREV" "$line")"
        ABSENT=$((ABSENT+1))
    fi

done < "$SHA_LIST_FILE"

if [ $QUIET -eq 0 ]; then
    echo ""
fi
echo "Summary"
echo "_______"
printf "%-7s: %d\n" "EXISTS" ${EXISTS:-0}
printf "%-7s: %d\n" "REVIEW" ${REVIEW:-0}
printf "%-7s: %d\n" "ABSENT" ${ABSENT:-0}
printf "%-7s: %d\n" "BADSHA" ${BADSHA:-0}
printf "%-7s: %d\n" "Total"  ${TOTAL:-0}
