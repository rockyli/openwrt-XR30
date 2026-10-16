#!/usr/bin/env python3
"""Check HTTPS dependencies in the actual XR30 device rootfs, without executing it."""

import argparse
import os
import shlex
from pathlib import Path


REQUIRED_PACKAGES = (
    "uhttpd", "uhttpd-mod-ubus", "libustream-mbedtls20201210",
    "px5g-mbedtls", "luci", "luci-base",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def uci_sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        words = shlex.split(line, comments=True)
        if not words:
            continue
        if words[0] == "config":
            current = {}
            if len(words) == 3:
                sections[words[1], words[2]] = current
        elif words[0] in ("option", "list") and current is not None:
            require(len(words) == 3, "Malformed uhttpd UCI directive")
            current.setdefault(words[1], []).append(words[2])
    return sections


def check(rootfs, manifest):
    packages = {line.split(" - ", 1)[0] for line in manifest.read_text().splitlines()}
    for package in REQUIRED_PACKAGES:
        require(package in packages, f"HTTPS package missing from device image: {package}")
    for name in ("usr/sbin/uhttpd", "usr/sbin/px5g", "etc/init.d/uhttpd", "www/cgi-bin/luci"):
        path = rootfs / name
        require(path.is_file() and os.access(path, os.X_OK), f"HTTPS executable missing: {name}")
    for name in ("lib/libustream-ssl.so", "usr/lib/uhttpd_ubus.so"):
        path = rootfs / name
        require(path.is_file() and path.stat().st_size > 0, f"HTTPS runtime missing: {name}")

    sections = uci_sections((rootfs / "etc/config/uhttpd").read_text())
    main = sections.get(("uhttpd", "main"), {})
    for key, expected in {
        "listen_http": ["0.0.0.0:80", "[::]:80"],
        "listen_https": ["0.0.0.0:443", "[::]:443"],
        "cert": ["/etc/uhttpd.crt"], "key": ["/etc/uhttpd.key"],
    }.items():
        require(main.get(key) == expected, f"Unexpected default uhttpd {key}")
    require(main.get("enabled", ["1"]) == ["1"], "Default uhttpd is disabled")
    require(("cert", "defaults") in sections, "Native certificate defaults missing")

    keep = (rootfs / "lib/upgrade/keep.d/uhttpd").read_text().splitlines()
    for name in ("/etc/uhttpd.crt", "/etc/uhttpd.key"):
        require(name in keep, f"Generated HTTPS credential not in upgrade keep list: {name}")
        path = rootfs / name.lstrip("/")
        require(not path.exists() and not path.is_symlink(),
                f"Do not embed per-device HTTPS credentials in firmware: {name}")
    print("HTTPS_IMAGE_OK: packages, native defaults and credential preservation checked; hardware testing pending")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    check(args.rootfs, args.manifest)
