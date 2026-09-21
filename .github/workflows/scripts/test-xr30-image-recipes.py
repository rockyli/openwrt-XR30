#!/usr/bin/env python3
"""Evaluate the real Make definitions to catch inherited DTB paths before a build."""

import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]


class ImageRecipes(unittest.TestCase):
    def test_profile_dtb_paths(self):
        source = (ROOT / "target/linux/mediatek/image/filogic.mk").read_text()
        profiles = ("cmcc_rax3000m", "cmcc_xr30")
        definitions = []
        for profile in profiles:
            match = re.search(
                rf"^define Device/{profile}\n.*?^endef$", source, re.M | re.S
            )
            self.assertIsNotNone(match, profile)
            definitions.append(match.group())
        makefile = "KDIR := /test/kernel\nCONFIG_TARGET_ROOTFS_PARTSIZE := 448\n"
        makefile += "\n".join(definitions) + "\n"
        # OpenWrt expands each profile inside eval, then parses its := assignments
        # in order. A later DEVICE_DTS assignment does not update earlier recipes.
        for profile in profiles:
            makefile += f"$(eval $(call Device/{profile}))\n"
            for variable in ("DEVICE_DTS", "KERNEL_INITRAMFS", "IMAGE/sysupgrade.itb"):
                makefile += f"$(info {profile}|{variable}|$({variable}))\n"
        makefile += "all:;@:\n"
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "Makefile"
            path.write_text(makefile)
            result = subprocess.run(
                ["make", "--no-print-directory", "-f", str(path)],
                check=True, text=True, capture_output=True, cwd=temp,
            )
        values = {}
        for line in result.stdout.splitlines():
            profile, variable, value = line.split("|", 2)
            values[profile, variable] = value
        for profile, dts in (("cmcc_rax3000m", "mt7981b-cmcc-rax3000m"),
                             ("cmcc_xr30", "mt7981b-cmcc-xr30")):
            with self.subTest(profile=profile):
                self.assertEqual(values[profile, "DEVICE_DTS"], dts)
                for variable in ("KERNEL_INITRAMFS", "IMAGE/sysupgrade.itb"):
                    paths = re.findall(r"/test/kernel/image-[\w-]+\.dtb", values[profile, variable])
                    self.assertEqual(paths, [f"/test/kernel/image-{dts}.dtb"], variable)


if __name__ == "__main__":
    unittest.main()
