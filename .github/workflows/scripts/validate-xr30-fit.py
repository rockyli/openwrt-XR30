#!/usr/bin/env python3
"""Check XR30 model and the existing eMMC boot selection in a built FIT."""

import pathlib
import struct
import subprocess
import sys
import tempfile


def prop(path, node, name, kind="s"):
    return subprocess.check_output(
        ["fdtget", "-t", kind, str(path), node, name], text=True
    ).strip()


def extract(fit, node, dest):
    properties = subprocess.check_output(
        ["fdtget", "-p", str(fit), node], text=True
    ).splitlines()
    if "data" in properties:
        data = bytes(int(x, 16) for x in prop(fit, node, "data", "bx").split())
    else:
        size = int(prop(fit, node, "data-size", "x"), 16)
        raw = fit.read_bytes()
        if "data-position" in properties:
            start = int(prop(fit, node, "data-position", "x"), 16)
        else:
            total = struct.unpack_from(">I", raw, 4)[0]
            start = ((total + 3) & ~3) + int(prop(fit, node, "data-offset", "x"), 16)
        if start < 0 or size <= 0 or start + size > len(raw):
            raise ValueError("FIT external DTB data is out of bounds")
        data = raw[start:start + size]
    dest.write_bytes(data)


def check(fit):
    overlay = "mt7981b-cmcc-rax3000m-emmc"
    if prop(fit, "/configurations", "default") != "config-1":
        raise ValueError("Unexpected default FIT configuration")
    base_node = prop(fit, "/configurations/config-1", "fdt")
    overlay_node = prop(fit, "/configurations/" + overlay, "fdt")
    if base_node != "fdt-1" or overlay_node != "fdt-" + overlay:
        raise ValueError("Existing U-Boot eMMC selection no longer resolves")
    with tempfile.TemporaryDirectory() as temp:
        base = pathlib.Path(temp) / "base.dtb"
        dtbo = pathlib.Path(temp) / "emmc.dtbo"
        merged = pathlib.Path(temp) / "merged.dtb"
        extract(fit, "/images/" + base_node, base)
        extract(fit, "/images/" + overlay_node, dtbo)
        subprocess.run(
            ["fdtoverlay", "-i", str(base), "-o", str(merged), str(dtbo)], check=True
        )
        for tree in (base, merged):
            model = prop(tree, "/", "model")
            if model != "XR30":
                raise ValueError(f"{fit.name}: {tree.name} model is {model!r}; expected 'XR30'")
            if prop(tree, "/", "compatible").split() != ["cmcc,rax3000m", "mediatek,mt7981"]:
                raise ValueError("RAX3000M runtime compatibility changed")
        prop(merged, "/chosen", "rootdisk", "x")
    print(f"{fit.name}: XR30 model and existing eMMC FIT selection verified")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: validate-xr30-fit.py IMAGE.itb [IMAGE.itb ...]")
    for argument in sys.argv[1:]:
        check(pathlib.Path(argument))
