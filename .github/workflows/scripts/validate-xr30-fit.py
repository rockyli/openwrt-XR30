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


def check_leds(tree):
    nodes = subprocess.check_output(
        ["fdtget", "-l", str(tree), "/gpio-leds"], text=True
    ).split()
    if set(nodes) != {"led-2", "led-white"}:
        raise ValueError(f"{tree.name}: expected only XR30 red and white LEDs, got {nodes}")
    pio = prop(tree, "/__symbols__", "pio")
    controller = int(prop(tree, pio, "phandle", "x"), 16)
    # Linux LED binding: WHITE=0, RED=1; GPIO_ACTIVE_LOW=1.
    for node, gpio, color in (("led-2", 35, 1), ("led-white", 34, 0)):
        path = "/gpio-leds/" + node
        cells = [int(cell, 16) for cell in prop(tree, path, "gpios", "x").split()]
        if cells != [controller, gpio, 1]:
            raise ValueError(f"{tree.name}: unexpected GPIO wiring for {node}: {cells}")
        if int(prop(tree, path, "color", "x"), 16) != color or prop(tree, path, "function") != "status":
            raise ValueError(f"{tree.name}: unexpected LED color/function for {node}")
    for alias, node in (("led-boot", "led-2"), ("led-failsafe", "led-2"),
                        ("led-running", "led-white"), ("led-upgrade", "led-white")):
        if prop(tree, "/aliases", alias) != "/gpio-leds/" + node:
            raise ValueError(f"{tree.name}: unexpected {alias} LED")


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
            check_leds(tree)
        prop(merged, "/chosen", "rootdisk", "x")
    print(f"{fit.name}: XR30 model, red/white LEDs and existing eMMC FIT selection verified")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: validate-xr30-fit.py IMAGE.itb [IMAGE.itb ...]")
    for argument in sys.argv[1:]:
        check(pathlib.Path(argument))
