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
The separate manual `XR30 - Build development firmware` workflow builds its
exact triggering commit, verifies pinned feeds, and preserves revision records,
expanded configuration, package outputs and checksums. The official baseline
workflow continues to build its fixed upstream source independently.

CI checks both FIT files for the runtime model, compatibility identity and
bootloader-selected eMMC configuration. A successful build is not hardware
validation. Treat outputs as candidates until the physical tests below pass.
The 448 MiB setting is specific to the recorded production partition layout;
the unchanged compatibility string cannot distinguish all RAX3000M variants.

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
