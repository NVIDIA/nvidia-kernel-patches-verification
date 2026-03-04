# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

# verify-upstream-commits

A script to check if a list of upstream Linux kernel commit SHAs are present (cherry-picked, backported, or otherwise) in a target branch, or to identify their status in your local repository.

## Features
- Checks if each upstream SHA is present in the target branch (or current branch by default).
- Detects cherry-picked or backported commits by matching commit titles and trailers.
- Compares patch content, ignoring commit message trailers and context-only changes.
- **Match by title (`-t`)**: find the reference commit on upstream by title instead of list SHA; useful when the branch was rebased and list SHAs are no longer in upstream history.
- Outputs a summary of results: EXISTS, REVIEW, ABSENT, BADSHA.
- Supports quiet mode, dry run, and verbose (debug) output.
- Flexible: can specify branch and upstream (URL or remote/branch).

## Usage

```
Usage: ./verify-upstream-commits [-b branch] [-U upstream] [-q] [-n] [-v] [-t] <sha_list_file>
  -b branch         Branch to check (default: current branch)
  -U upstream       Upstream source: URL or remote/branch (default: https://github.com/torvalds/linux, branch master)
  -q                Quiet mode (only summary)
  -n                Dry run (show what would be checked, don't execute)
  -v                Verbose mode (enable debug output)
  -t                Match by title: find reference commit on upstream by title instead of list SHA
```

## Examples

### Example 1: Standard Output
```
$ ./verify-upstream-commits commits 
EXISTS  (56501181) 97717a1f283fee4e886bbe96c6a0ca460f71a4ab
REVIEW  (ba6996be) 0ce5c2477af2
EXISTS  (90ee442a) 5778c75703c6
EXISTS  (f908b2b2) 67db79dc1a41
EXISTS  (5145a8ed) 54ce69e36c71 iommufd: Allow hwpt_id to carry viommu_id for IOMMU_HWPT_INVALIDATE
EXISTS  (657cf537) 4f2e59ccb698
EXISTS  (a56c9461) c747e67978ff
EXISTS  (ab903572) d6563aa2a830
EXISTS  (5b44dcfd) 576ad6eb45d6
EXISTS  (88fa2765) 49ad12771924
EXISTS  (f1bc7553) b047c0644f4e
REVIEW  (bae492fb) abc7b3f1f056 RDMA/mlx5: Fix a WARN during dereg_mr for DM type
BADSHA  (--------) d4f4ca57cab76c3b61821e6f08e9be7fb8e37c08
EXISTS  (2346c504) 5426a78bebefbb32643ee85320e977f3971c5521
REVIEW  (210ab445) 927dabc9aa4dbebf92b34da9b7acd7d8d5c6331b
ABSENT  (--------) ee512922ddd7
EXISTS  (be3cf53c) 7ce555252c711f7520be42abba5c7401b3b68456
EXISTS  (d9b95309) c0dec4b848ce5110e95095d0d0ae46724beb70ec
EXISTS  (493a3479) 3d49020a327cd7d069059317c11df24e407ccfa3
BADSHA  (--------) d069059317c1
EXISTS  (1751266f) df49881956bab88298e754c73010196b49af6733
EXISTS  (136a8066) 136a8066676e593cd29627219467fc222c8f3b04
EXISTS  (d73cf5ff) d73cf5ff743b5a8de6fa20651baba5bd56ba98a3
EXISTS  (52acd7d8) 52acd7d8a4130ad4dda6540dbbb821a92e1c0138

Summary
_______
EXISTS : 18
REVIEW : 3
ABSENT : 1
BADSHA : 2
Total  : 24
```

### Example 2: Quiet Mode and Custom Branch
```
$ ./verify-upstream-commits -q -b origin/linux grace_iov_patches_v04
Summary
_______
EXISTS : 605
REVIEW : 0
ABSENT : 0
BADSHA : 0
Total  : 605
```

### Example 3: Match by Title (for rebased branches)
When your branch was rebased and list SHAs are no longer in upstream history, use `-t` so the script finds the reference commit on upstream by matching the commit title (from the list line or from the SHA if present in the repo):

```
$ ./verify-upstream-commits -t -U origin/linux-nvidia-6.18 vera-baremetal-addendum.txt
```

List lines should use the format `SHA | TITLE` so that when the list SHA is not in upstream, the title is still available for the search.

## Requirements
- Bash
- git
- A Linux kernel git repository (or set the LINUX_GIT environment variable to point to one)

## Notes
- The input file should contain one entry per line: **SHA** in the first column, optionally followed by **` | TITLE`** (pipe and commit subject). Blank lines and lines starting with `#` are ignored. The `SHA | TITLE` format is recommended when using `-t` (match by title).
- **EXISTS**: the patch is on the branch (directly or as a cherry-pick/backport with matching diff).
- **REVIEW**: a commit with matching title was found but the diff differs, or the title matches and there is no backport trailer (e.g. backported from list).
- **ABSENT**: no commit on the branch has a matching title.
- **BADSHA**: the list SHA is not in the given upstream (and with `-t`, no commit on upstream matches the title).
- When `-U` is a URL, the script adds a temporary remote, fetches the default branch, and removes the remote on exit.
