#!/usr/bin/env python3
"""Derive XR30 settings from a pinned release and fail closed on ABI drift."""

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = ROOT / "config/xr30-official"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def config(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(CONFIG_\w[\w-]*)=(.*)", line)
        unset = re.fullmatch(r"# (CONFIG_\w[\w-]*) is not set", line)
        if match:
            result[match[1]] = match[2]
        elif unset:
            result[unset[1]] = "n"
    return result


def baseline():
    lock = json.loads((OFFICIAL / "lock.json").read_text())
    for name in ("config.buildinfo", "feeds.buildinfo", "version.buildinfo"):
        require(hashlib.sha256((OFFICIAL / name).read_bytes()).hexdigest()
                == lock["sha256"][name], f"Official snapshot changed: {name}")
    require((ROOT / "feeds.conf.default").read_bytes()
            == (OFFICIAL / "feeds.buildinfo").read_bytes(), "Feed revisions differ from official release")
    return lock


def seed_values():
    baseline()
    # Device selection and installed userspace packages are product choices.
    # Keep official kernel/build defaults, overriding only the explicit XR30 seed.
    values = {k: v for k, v in config((OFFICIAL / "config.buildinfo").read_text()).items()
              if not k.startswith(("CONFIG_TARGET_DEVICE_", "CONFIG_PACKAGE_"))}
    values.update(config((ROOT / "config/xr30.config").read_text()))
    return values


def write_seed(destination):
    destination.write_text("".join(
        f"# {k} is not set\n" if v == "n" else f"{k}={v}\n"
        for k, v in seed_values().items()))


def check_config(path):
    actual = config(path.read_text())
    # Kconfig must retain every chosen setting. CI supplies a provenance code.
    for key, expected in seed_values().items():
        if key == "CONFIG_VERSION_CODE":
            continue
        require(actual.get(key, "n") == expected,
                f"Kconfig changed {key}: expected {expected}, got {actual.get(key)}")
    devices = [k for k, v in actual.items()
               if re.match(r"CONFIG_TARGET_(?:DEVICE_)?mediatek_filogic_DEVICE_", k) and v == "y"]
    require(devices == ["CONFIG_TARGET_DEVICE_mediatek_filogic_DEVICE_cmcc_xr30"],
            f"Unexpected selected devices: {devices}")
    print("Official build defaults and XR30 overrides survived defconfig")


def one(paths, label):
    paths = list(paths)
    require(len(paths) == 1, f"Expected one {label}, found {paths}")
    return paths[0]


def check_kernel(build, output):
    lock = baseline()
    kernel = lock["kernel"]
    linux = one(build.glob("build_dir/target-*/linux-mediatek_filogic/linux-*/.vermagic"), "kernel ABI file").parent
    output.mkdir(parents=True, exist_ok=True)
    for name in (".vermagic", ".config", ".config.set"):
        (output / ("linux" + name)).write_bytes((linux / name).read_bytes())
    actual = (linux / ".vermagic").read_text().strip()
    report = {"expected": kernel, "actual_vermagic": actual,
              "matched": actual == kernel["vermagic"]}
    (output / "kernel-abi-check.json").write_text(json.dumps(report, indent=2) + "\n")
    require(linux.name == "linux-" + kernel["version"], "Wrong kernel version")
    require(report["matched"], f"Kernel ABI mismatch: {actual} != {kernel['vermagic']}")
    print(f"Kernel ABI matches official release: {kernel['version']} / {actual}")


def check_image(build, output):
    lock = baseline()
    kernel = lock["kernel"]
    target = build / "bin/targets/mediatek/filogic"
    profiles = json.loads((target / "profiles.json").read_text())
    require(profiles["linux_kernel"] == kernel, "Image kernel metadata differs from official release")
    require(set(profiles["profiles"]) == {"cmcc_xr30"}, "Unexpected image profiles")
    manifest = (output / "xr30-installed-packages.manifest").read_text()
    packages = dict(line.split(" - ", 1) for line in manifest.splitlines())
    version = f"{kernel['version']}~{kernel['vermagic']}-r{kernel['release']}"
    require(packages.get("kernel") == version, "Installed kernel package ABI differs from official release")
    for package in ("kmod-tun", "kmod-inet-diag", "kmod-nft-tproxy", "tailscale",
                    "luci-app-tailscale-community", "luci-app-openclash"):
        require(package not in packages, f"Optional package unexpectedly preinstalled: {package}")
    rootfs = one(build.glob("build_dir/target-*/linux-mediatek_filogic/target-dir-*"), "device rootfs")
    feed = (rootfs / "etc/apk/repositories.d/distfeeds.list").read_text()
    expected = (f"{lock['base_url']}/kmods/{kernel['version']}-{kernel['release']}-"
                f"{kernel['vermagic']}/packages.adb")
    kmod_feeds = [line for line in feed.splitlines() if "/kmods/" in line]
    require(kmod_feeds == [expected], f"Wrong installed kmod feed: {kmod_feeds}")
    (output / "distfeeds.list").write_text(feed)
    print("Image metadata, installed kernel and official kmod feed agree")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "config", "kernel", "image"))
    parser.add_argument("--build", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=ROOT / ".config")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "seed":
        write_seed(args.config)
    elif args.phase == "config":
        check_config(args.config)
    else:
        require(args.output is not None, "--output is required")
        (check_kernel if args.phase == "kernel" else check_image)(args.build, args.output)


if __name__ == "__main__":
    main()
