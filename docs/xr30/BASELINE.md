# Official RAX3000M baseline build

The workflow `.github/workflows/rax3000m-baseline.yml` builds the existing
official RAX3000M profile from fixed OpenWrt v25.12.5 source. It does not build
the changing tip of this repository, and does not add XR30 device support.

## Inputs

- OpenWrt commit: `f0a60eee2fe051741c643ea6118718aae1ef17fb`.
- Feeds: the exact commits in that release's `feeds.conf.default`; checked after fetching.
- Target: `mediatek/filogic`, device `cmcc_rax3000m`.
- Packages: device defaults plus `luci`; no custom applications or credentials.
- Images: squashfs sysupgrade FIT and initramfs recovery FIT.
- Root filesystem partition setting: 448 MiB, matching the tested eMMC layout.
- Runner: disposable GitHub-hosted Ubuntu 24.04; 350-minute job limit.

The checkout contains no custom `files/` overlay. There are no credential inputs,
custom root passwords, SSH keys, enrollment tokens or device calibration blobs.

## Run

Once the workflow is committed, open **Actions > RAX3000M - Build official
baseline > Run workflow**, select `xr30-25.12`, and start. There is no `dry_run`
option. This is a full source build and can take hours. It uses no build cache
for the first baseline. Host package versions can change, so pinned OpenWrt and
feed commits alone do not guarantee byte-identical rebuilds.

A successful run uploads an artifact named
`rax3000m-25.12.5-baseline-<run>-<attempt>` containing the two images, checksums,
expanded and minimal build configurations, revision records, package manifests,
FIT structure reports, package outputs and diagnostic logs. Artifacts expire
after 14 days; download them to retain the baseline. No GitHub Release is created.

An unsuccessful run can also upload diagnostic artifacts. The existence of an
artifact is not evidence of a successful build: check the overall job result.
The workflow validates selected-device configuration and image structure, but
hardware testing is still a separate step. Do not flash bootloader or GPT
artifacts when testing an ordinary system upgrade.

## Packages and upgrades

This is a community build with official source and device support, not an
official release binary. Kernel ABI/package selection and signing may differ
from published binaries. Preserve the included matching package outputs;
do not assume official kmods can be installed unchanged. The archive does not
include private signing keys; feed publication and trust configuration require
separate work if these packages will be distributed or installed later.

Before installing an image on a device, transfer it, verify SHA256SUMS and run
`sysupgrade -T` on the device. A successful image check does not replace backups
or a recovery path. Evaluate actual flashing separately after the baseline
build succeeds.
