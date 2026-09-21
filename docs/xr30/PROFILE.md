# XR30 personal firmware profile

This initial profile changes the runtime model to exactly `XR30` and creates
the build target `cmcc_xr30`. It reuses the existing RAX3000M hardware description,
packages, partition handling and upgrade implementation. It is a personal
firmware customization, not yet an independent upstream device port.

The base DTS includes the RAX3000M DTS and overrides the model and LEDs. Runtime
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

The seed combines the pinned official `config/xr30-official/config.buildinfo`
with `config/xr30.config`: Filogic, XR30, LuCI, squashfs, initramfs,
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

CI checks both FIT files for the runtime model, red/white LEDs, compatibility identity and
bootloader-selected eMMC configuration. A successful build is not hardware
validation. Treat outputs as candidates until the physical tests below pass.
The 448 MiB setting is specific to the recorded production partition layout;
the unchanged compatibility string cannot distinguish all RAX3000M variants.

## Official kernel module compatibility

The build now targets the official 25.12.5 Filogic kernel module repository.
The [release lock](../../config/xr30-official/lock.json) records the official
source commit, kernel version/release/ABI, architecture and build timestamp.
It also records the published SHA256 checksums of the official build metadata;
config, feeds and version snapshots are kept alongside it. The official
[config.buildinfo](https://downloads.openwrt.org/releases/25.12.5/targets/mediatek/filogic/config.buildinfo)
and
[profiles.json](https://downloads.openwrt.org/releases/25.12.5/targets/mediatek/filogic/profiles.json)
are the sources of these settings. Upgrading the release requires reviewing and
updating the lock and snapshots together, not just changing the repository URL.

Generate the configuration with:

```sh
python3 .github/workflows/scripts/xr30-official-abi.py seed
make defconfig
python3 .github/workflows/scripts/xr30-official-abi.py config
```

The generator retains official build/kernel options, including `ALL_KMODS`,
`ALL_NONSHARED`, `BUILDBOT`, per-device rootfs and disabled `KERNEL_KALLSYMS`.
It replaces the official device list and installed userspace selections with
the XR30 seed. Only the XR30 image is produced. SDK, ImageBuilder and toolchain
archive outputs are disabled; the underlying tools are built from the pinned
source. The official build timestamp is retained. XR30 model, LED definitions,
LAN defaults and version display remain customized.

All available kernel module packages are selected for compilation, but optional
modules such as `kmod-tun`, `kmod-inet-diag` and `kmod-nft-tproxy` are not installed
in the firmware. Tailscale, OpenClash and their LuCI applications also remain
separately installed. Standard dnsmasq is retained; OpenClash still requires
its userspace dependencies, including dnsmasq-full, when installed later.
Attended Sysupgrade is not preinstalled: the public service does not know the
custom XR30 profile, regardless of kernel ABI compatibility.

CI checks source files affecting the kernel/toolchain against the locked
release, validates the expanded configuration, then configures the real kernel
and stops before image generation if its ABI differs from the official value.
It preserves the actual Linux config and mismatch report for diagnosis. No
vermagic override or forced dependency installation is used.

After building, CI checks `profiles.json`, the kernel package installed in the
actual XR30 rootfs, and its generated official kmod feed URL. Using a separate
copy of that rootfs and the installed signing keys, it updates official APK
indexes and simulates installing Tailscale, its LuCI application and the three
optional modules. The firmware itself remains unchanged by that check. Image
validation is marked successful only after all checks pass. Actual module
loading and application behavior still need device testing.

Candidate `59746ec748a5` booted and reported XR30, but its minimal kernel config
had a different ABI and no matching module feed. Merely adding the official
feed to that older firmware cannot fix it. Candidate `209520e8ff3f` takes the
interim approach of embedding selected modules; it does not implement official
ABI alignment. Upgrade to a successfully validated build from this new route
before using the official module feed. Do not mix modules across incompatible
candidates. Keep the matching packages artifact with each firmware as a record;
locally built APKs have separate signing trust from the official repository.

On the device, after upgrading with settings preserved:

```sh
apk update
apk add --simulate kmod-tun tailscale luci-app-tailscale-community
apk add kmod-tun tailscale luci-app-tailscale-community
modprobe tun
test -c /dev/net/tun && echo 'TUN device is available'
```

A successful CI simulation is not a hardware test. Confirm module loading,
Tailscale startup and preserved configuration on the intended device before
considering this compatibility work validated.

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

## LEDs and buttons

The DDR4/eMMC XR30 (RAX3000Z enhanced version) uses a white projection LED on
GPIO34 and a red LED on GPIO35, both active low. The XR30 DTS removes the
inherited RAX3000M green/blue LED nodes on GPIO9/GPIO12, retains the red LED,
and adds `white:status`. Boot/failsafe uses red; running/upgrade uses white.
These are Linux status indicators; this change does not alter bootloader LEDs.

The user verified both LED channels by temporary on/off tests while running
the official RAX3000M firmware. RESET on GPIO1 reported press/release events
with its destructive actions temporarily replaced by logging. Actual factory
reset behavior was not tested, and the user restored the original handlers.
The physical Mesh button produced no event in that test. At the user's request,
further Mesh investigation is deferred and its inherited GPIO0/BTN_9/EV_SW
definition is unchanged. It is not presented as a working WPS button.

## Validation status and remaining work

Before this change, the user reports normal WAN/LAN and dual-band Wi-Fi on the
official RAX3000M image. LED electrical behavior and RESET events are confirmed
as described above. Candidate `59746ec748a5` has now booted on the DDR4/eMMC
device and reported model `XR30` with board compatibility `cmcc,rax3000m`.
Boot/status indication in the updated XR30 image, actual
factory reset, and Mesh behavior remain unverified. These results do not
establish that subsequent XR30 builds work or that application installation
has been validated after the kernel module change.

For each candidate, check the checksum and run `sysupgrade -T` on the intended
device before considering a normal system upgrade. Confirm the target device's
layout and recovery path first. Record cold boot, model display, every Ethernet
port, both Wi-Fi bands, LEDs, reset, upgrade and rollback results.

Future upstream work requires confirmed manufacturer/product identity,
documented hardware differences and complete installation/recovery/test notes.
Do not present this display customization as upstream-ready device support.
