# CMCC XR30 / RAX3000Z development

This public repository starts from official OpenWrt. The initial development
branch is based on `v25.12.5` (`f0a60eee2fe051741c643ea6118718aae1ef17fb`).
The initial [XR30 personal profile](PROFILE.md) adds an XR30 build option and
runtime model while retaining RAX3000M compatibility. It is not yet an
independent upstream device port and has not produced hardware-tested XR30
release images.

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Unmodified official development branch |
| `openwrt-25.12` | Unmodified official 25.12 stable branch |
| `xr30-25.12` | Project default branch: reviewed XR30 changes and automation |

Other branches imported from upstream are retained, but are not automatically
synchronized by this workflow.

## Initial activation

1. In repository **Settings > General > Default branch**, select `xr30-25.12`.
2. In **Actions**, enable workflows if GitHub displays an enable prompt.
3. Select **XR30 - Sync upstream branches > Run workflow** on `xr30-25.12`.
   Leave **dry_run** enabled for the first check.
4. Review the job summary. Run again with **dry_run** disabled to update the
   tracking branches, or wait for the daily schedule.

The schedule is daily at 19:17 UTC / 03:17 UTC+8. GitHub schedules can be delayed;
they run only when this workflow is present on the default branch. Public
repositories without activity for 60 days can have schedules disabled.

The workflow uses GitHub's short-lived `GITHUB_TOKEN`, not a personal token.
It fetches official Git objects without checking out or executing upstream code.
Only `main` and `openwrt-25.12` can be updated, through an atomic non-forced push.
A divergent branch causes failure before any push. Repository rules or token
restrictions can also reject the push; investigate the failure without forcing
updates or placing credentials in files. A dry run does not guarantee that all
server-side checks for a real push will pass.

## Incorporating updates

The daily job does **not** merge updates into `xr30-25.12`, open PRs, build
firmware, synchronize tags, or publish releases. Those are separate steps.

After the first reproducible build is established, review upstream changes
weekly or at each official 25.12.x release. Create a temporary integration branch
from `xr30-25.12`, merge the selected official commit or verified release tag,
resolve conflicts there, and open a PR targeting `xr30-25.12`. Preserve merge
ancestry when merging upstream synchronization PRs; do not squash those merges.
Build and inspect the candidate; publish an immutable XR30 release tag only
after hardware testing. Do not merge official `main` into this stable branch.

Pin and record feed commits as well as the OpenWrt commit. The fixed-source
[baseline build](BASELINE.md) and the manual [XR30 development build](PROFILE.md)
serve different purposes. Artifact review and hardware testing remain required.

## Public content

See [repository instructions](../../AGENTS.md). Device backups and credentials
belong outside the checkout. `.gitignore` does not sanitize existing tracked
files or prevent deliberately forced additions. Review exact diffs and release
contents, including logs and firmware defaults, before publication.
