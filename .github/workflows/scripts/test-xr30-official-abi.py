#!/usr/bin/env python3
"""Exercise the release lock and reject incompatible kernel/image artifacts."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("abi", Path(__file__).with_name("xr30-official-abi.py"))
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


class OfficialABI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.lock = abi.baseline()
        self.kernel = self.lock["kernel"]

    def test_seed_preserves_kernel_defaults_and_limits_images(self):
        path = self.root / "config"
        abi.write_seed(path)
        abi.check_config(path)
        values = abi.config(path.read_text())
        self.assertEqual(values["CONFIG_ALL_KMODS"], "y")
        self.assertEqual(values["CONFIG_KERNEL_KALLSYMS"], "n")
        self.assertEqual(values["CONFIG_PACKAGE_kmod-tun"], "m")
        self.assertEqual(values["CONFIG_TARGET_ALL_PROFILES"], "n")
        self.assertNotIn("CONFIG_PACKAGE_luci-app-attendedsysupgrade", values)
        path.write_text(path.read_text().replace("CONFIG_ALL_KMODS=y", "# CONFIG_ALL_KMODS is not set"))
        with self.assertRaisesRegex(ValueError, "CONFIG_ALL_KMODS"):
            abi.check_config(path)

    def test_kernel_mismatch_retains_diagnostics_and_fails(self):
        linux = self.root / f"build_dir/target-test/linux-mediatek_filogic/linux-{self.kernel['version']}"
        linux.mkdir(parents=True)
        (linux / ".config").write_text("CONFIG_TUN=m\n")
        (linux / ".config.set").write_text("CONFIG_TUN=m\n")
        (linux / ".vermagic").write_text(self.kernel["vermagic"] + "\n")
        abi.check_kernel(self.root, self.output)
        (linux / ".vermagic").write_text("a64cdc69add322a87084e41c2857026c\n")
        with self.assertRaisesRegex(ValueError, "Kernel ABI mismatch"):
            abi.check_kernel(self.root, self.output)
        self.assertFalse(json.loads((self.output / "kernel-abi-check.json").read_text())["matched"])
        self.assertTrue((self.output / "linux.config.set").exists())

    def image_fixture(self):
        target = self.root / "bin/targets/mediatek/filogic"
        target.mkdir(parents=True)
        (target / "profiles.json").write_text(json.dumps({
            "linux_kernel": self.kernel, "profiles": {"cmcc_xr30": {}}}))
        manifest = self.output / "xr30-installed-packages.manifest"
        k = self.kernel
        manifest.write_text(f"kernel - {k['version']}~{k['vermagic']}-r{k['release']}\n")
        feed = self.root / "build_dir/target-test/linux-mediatek_filogic/target-dir-12345678/etc/apk/repositories.d/distfeeds.list"
        feed.parent.mkdir(parents=True)
        feed.write_text(f"{self.lock['base_url']}/kmods/{k['version']}-{k['release']}-{k['vermagic']}/packages.adb\n")
        return manifest, feed

    def test_image_rejects_wrong_feed_and_preinstalled_optional_module(self):
        manifest, feed = self.image_fixture()
        abi.check_image(self.root, self.output)
        good_feed = feed.read_text()
        feed.write_text(good_feed.replace(self.kernel["vermagic"], "incorrect"))
        with self.assertRaisesRegex(ValueError, "Wrong installed kmod feed"):
            abi.check_image(self.root, self.output)
        feed.write_text(good_feed)
        manifest.write_text(manifest.read_text() + "kmod-tun - 6.12.94-r1\n")
        with self.assertRaisesRegex(ValueError, "unexpectedly preinstalled"):
            abi.check_image(self.root, self.output)

    def test_image_rejects_incompatible_installed_kernel(self):
        manifest, _ = self.image_fixture()
        manifest.write_text("kernel - 6.12.94~incorrect-r1\n")
        with self.assertRaisesRegex(ValueError, "Installed kernel package ABI"):
            abi.check_image(self.root, self.output)


if __name__ == "__main__":
    unittest.main()
