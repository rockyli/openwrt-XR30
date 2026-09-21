# XR30 personal firmware profile

This initial profile changes the runtime model to exactly `XR30` and creates
the build target `cmcc_xr30`. It reuses the existing RAX3000M hardware description,
packages, partition handling and upgrade implementation. It is a personal
firmware customization, not yet an independent upstream device port.

The base DTS includes the RAX3000M DTS and overrides only `model`. Runtime
`compatible`, `board_name` and image `supported_devices` remain
`cmcc,rax3000m`. This is intentional: changing the compatibility identity would
also require a separately verified migration and board-script integration.
The existing RAX3000M profile remains available and unchanged.

Keep `config-1` and the original `mt7981b-cmcc-rax3000m-emmc` FIT overlay
configuration name: the installed OpenWrt eMMC bootloader selects them by name.
Both inherited storage overlays are retained to avoid narrowing the existing
RAX3000M compatibility metadata. XR30 hardware testing currently covers only
the DDR4/eMMC variant. No new BL2, FIP or GPT artifacts are advertised by this
profile; it uses the already installed bootloader and partition table.

## Build

The seed is `config/xr30.config`: Filogic, XR30, LuCI, squashfs, initramfs,
448 MiB rootfs partition setting, and a `25.12.5-XR30` version suffix.
`CONFIG_IMAGEOPT=y` is required for Kconfig to retain the custom version
options. The runtime version uses `XR30`, while OpenWrt normalizes the version
portion of image filenames to lowercase (`25.12.5-xr30`).
The separate manual `XR30 - Build development firmware` workflow builds its
exact triggering commit, verifies pinned feeds, and preserves revision records,
expanded configuration, package outputs and checksums. The official baseline
workflow continues to build its fixed upstream source independently.

Builds can also be requested over SSH by pushing a new lightweight tag with
the prefix `xr30-ci-` at the exact development commit to test. For example,
create `xr30-ci-YYYYMMDD-NN` at the selected commit and push that tag explicitly.
Use a new tag for each request; never move a previous build tag. Ordinary branch
pushes do not trigger this XR30 workflow. These CI tags are not release tags and
do not match the repository's `v*` release workflow.

To cancel a specific XR30 development build over SSH, push a new lightweight
tag `xr30-cancel-RUN_ID` at a commit containing `xr30-cancel.yml`, substituting
the numeric Actions run ID. The control job checks the repository and workflow
before requesting cancellation. It uses an ephemeral GitHub token with Actions
write permission only in that job; the firmware build retains read-only access.
Cancellation tags do not trigger firmware builds or releases.

The inherited generic package and kernel workflows skip pushes to
`xr30-25.12`; their pull-request checks and other branch rules are unchanged.
The dedicated XR30 workflow still requires a CI tag or manual dispatch.

Both XR30 image recipes are reassigned after `DEVICE_DTS` is overridden.
The inherited RAX3000M recipes use immediate Make assignments, so changing
`DEVICE_DTS` alone leaves their FIT commands pointing at the RAX3000M DTB.
CI evaluates both profiles' actual Make definitions before building and then
checks the model in the resulting FIT images after applying the eMMC overlay.

CI checks both FIT files for the runtime model, compatibility identity and
bootloader-selected eMMC configuration. A successful build is not hardware
validation. Treat outputs as candidates until the physical tests below pass.
The 448 MiB setting is specific to the recorded production partition layout;
the unchanged compatibility string cannot distinguish all RAX3000M variants.

## Default LAN and DHCP

With a fresh configuration, LAN uses `192.168.10.1/24` (network
`192.168.10.0/24`, netmask `255.255.255.0`). Connect a computer configured to
obtain its address and DNS automatically to a LAN port; after normal boot it
should receive an address from `192.168.10.100` through `192.168.10.249`, with
a 12-hour lease. The router provides the default gateway and DNS service at
`192.168.10.1`. The WAN port does not serve DHCP.

The seed explicitly includes dnsmasq and uses OpenWrt's built-in
`TARGET_DEFAULT_LAN_IP_FROM_PREINIT` mechanism to generate the LAN address.
Preinit/failsafe therefore also uses `192.168.10.1`; automatic DHCP access is
the normal-boot behavior, not a failsafe guarantee. Standard dnsmasq LAN pool
settings remain unchanged. A DHCP lease does not itself guarantee Internet
access; WAN connectivity must be configured separately.

An upgrade that preserves settings retains existing LAN and DHCP settings.
These defaults take effect on a fresh installation or when configuration is
reset. Builds already running use their original source commit and do not
incorporate this change.

## Validation status and remaining work

Before this change, the user reports normal WAN/LAN and dual-band Wi-Fi on the
official RAX3000M image. LED and reset-button behavior remain untested. These
results do not establish that a newly built XR30 image works.

For each candidate, check the checksum and run `sysupgrade -T` on the intended
device before considering a normal system upgrade. Confirm the target device's
layout and recovery path first. Record cold boot, model display, every Ethernet
port, both Wi-Fi bands, LEDs, reset, upgrade and rollback results.

Future upstream work requires confirmed manufacturer/product identity,
documented hardware differences and complete installation/recovery/test notes.
Do not present this display customization as upstream-ready device support.
