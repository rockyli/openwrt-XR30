#!/usr/bin/env python3
"""Regression tests for clean-boot HTTPS and diagnostics; no hardware emulation."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("https_image", Path(__file__).with_name("check-xr30-https-image.py"))
IMAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMAGE)


class HTTPS(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text, executable=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if executable:
            path.chmod(0o755)
        return path

    def image_fixture(self):
        manifest = self.write("manifest", "".join(f"{p} - test\n" for p in IMAGE.REQUIRED_PACKAGES))
        for name in ("usr/sbin/uhttpd", "usr/sbin/px5g", "etc/init.d/uhttpd", "www/cgi-bin/luci"):
            self.write(name, "#!/bin/sh\nexit 0\n", True)
        for name in ("lib/libustream-ssl.so", "usr/lib/uhttpd_ubus.so"):
            self.write(name, "fixture")
        for source, target in (("uhttpd.config", "etc/config/uhttpd"),
                               ("uhttpd.upgrade", "lib/upgrade/keep.d/uhttpd")):
            self.write(target, (ROOT / "package/network/services/uhttpd/files" / source).read_text())
        return manifest

    def test_image_requires_real_files_and_packages(self):
        manifest = self.image_fixture()
        IMAGE.check(self.root, manifest)
        good = manifest.read_text()
        for package in IMAGE.REQUIRED_PACKAGES:
            with self.subTest(package=package):
                manifest.write_text(good.replace(f"{package} - test\n", ""))
                with self.assertRaisesRegex(ValueError, "package missing"):
                    IMAGE.check(self.root, manifest)
        manifest.write_text(good)
        (self.root / "usr/sbin/px5g").unlink()
        with self.assertRaisesRegex(ValueError, "executable missing"):
            IMAGE.check(self.root, manifest)

    def test_image_rejects_embedded_keys_bad_defaults_and_missing_keep(self):
        manifest = self.image_fixture()
        key = self.write("etc/uhttpd.key", "never ship this fixture")
        with self.assertRaisesRegex(ValueError, "embed per-device"):
            IMAGE.check(self.root, manifest)
        key.unlink()
        conf = self.root / "etc/config/uhttpd"
        good = conf.read_text()
        conf.write_text(good.replace("0.0.0.0:443", "0.0.0.0:4443"))
        with self.assertRaisesRegex(ValueError, "listen_https"):
            IMAGE.check(self.root, manifest)
        conf.write_text(good)
        self.write("lib/upgrade/keep.d/uhttpd", "/etc/uhttpd.crt\n")
        with self.assertRaisesRegex(ValueError, "keep list"):
            IMAGE.check(self.root, manifest)

    def test_native_init_clean_missing_partial_and_existing_credentials(self):
        # Run the actual upstream init control flow, replacing only the library
        # path and external procd/UCI/generator services. No source changes shipped.
        native = (ROOT / "package/network/services/uhttpd/files/uhttpd.init").read_text()
        self.write("native.init", native.replace("/lib/libustream-ssl.so", str(self.root / "tls.so")))
        self.write("tls.so", "fixture")
        self.write("generator", '''#!/bin/sh
printf 'called\n' >> "$TEST_ROOT/generator.calls"
while [ "$#" -gt 0 ]; do
    case "$1" in
        -keyout|-out) shift; printf 'generated\n' > "$1" ;;
    esac
    shift
done
''', True)
        harness = self.write("run-native.sh", '''#!/bin/sh
. "$TEST_ROOT/native.init"
PX5G_BIN="$TEST_ROOT/generator"
OPENSSL_BIN="$TEST_ROOT/no-openssl"
[ "$NO_GENERATOR" = 1 ] && PX5G_BIN="$TEST_ROOT/no-generator"
config_get() {
    local value="$4"
    case "$2:$3" in
        main:listen_https) value='0.0.0.0:443 [::]:443' ;;
        main:listen_http) value='0.0.0.0:80' ;;
        main:cert) value="$TEST_ROOT/cert" ;;
        main:key) value="$TEST_ROOT/key" ;;
    esac
    export "$1=$value"
}
config_get_bool() { export "$1=$4"; }
config_foreach() { "$1" defaults; }
config_list_foreach() { :; }
uci_get() { echo fixture; }
procd_open_instance() { :; }
procd_close_instance() { :; }
procd_set_param() { :; }
procd_append_param() { printf '%s\\n' "$*"; }
mkdir() { :; }
rm() { :; }
sync() { :; }
hexdump() { cat >/dev/null; printf 00000000; }
start_instance main
''', True)
        env = dict(os.environ, TEST_ROOT=str(self.root), NO_GENERATOR="1")
        def run():
            return subprocess.run(["sh", str(harness)], env=env, check=True, capture_output=True, text=True).stdout
        out = run()
        self.assertIn("command -p 0.0.0.0:80", out)
        self.assertNotIn("command -s", out)
        self.assertFalse((self.root / "cert").exists())
        env["NO_GENERATOR"] = "0"
        out = run()
        self.assertIn("command -s 0.0.0.0:443", out)
        self.assertIn("command -s [::]:443", out)
        self.assertEqual((self.root / "generator.calls").read_text(), "called\n")
        self.write("cert", "existing cert")
        self.write("key", "existing key")
        run()
        self.assertEqual((self.root / "cert").read_text(), "existing cert")
        self.assertEqual((self.root / "key").read_text(), "existing key")
        self.assertEqual((self.root / "generator.calls").read_text(), "called\n")
        (self.root / "cert").unlink()
        run()
        self.assertEqual((self.root / "key").read_text(), "generated\n")
        self.write("key", "")
        run()
        self.assertEqual((self.root / "generator.calls").read_text(), "called\n" * 3)

    def runtime_fixture(self):
        self.write("etc/init.d/uhttpd", "#!/bin/sh\nexit 0\n", True)
        self.write("usr/sbin/px5g", "#!/bin/sh\nexit 0\n", True)
        self.write("lib/libustream-ssl.so", "fixture")
        self.write("etc/uhttpd.crt", "fixture")
        self.write("etc/uhttpd.key", "fixture")
        table = "  sl local_address rem_address st\n 0: 00000000:01BB 00000000:0000 0A\n 1: 00000000:0050 00000000:0000 0A\n"
        self.write("proc/net/tcp", table)
        self.write("proc/net/tcp6", table)
        self.write("bin/uci", '''#!/bin/sh
case "$3" in
  uhttpd.main.cert) echo "$TEST_ROOT/etc/uhttpd.crt" ;;
  uhttpd.main.key) echo "$TEST_ROOT/etc/uhttpd.key" ;;
  uhttpd.main.listen_https) echo '0.0.0.0:443 [::]:443' ;;
  uhttpd.main.listen_http) echo '0.0.0.0:80 [::]:80' ;;
esac
''', True)
        self.write("bin/curl", '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_ROOT/curl.calls"\nprintf "%s" "${CURL_CODE:-200}"\nexit "${CURL_EXIT:-0}"\n', True)
        for command in ("awk", "grep"):
            (self.root / "bin" / command).symlink_to(shutil.which(command))
        script = (ROOT / "tests/xr30/check-management-https.sh").read_text()
        for prefix in ("/etc/", "/lib/", "/usr/", "/proc/"):
            script = script.replace(prefix, str(self.root) + prefix)
        return self.write("check.sh", script)

    def test_runtime_failures_are_distinct_and_aggregated(self):
        script = self.runtime_fixture()
        env = dict(os.environ, TEST_ROOT=str(self.root), PATH=str(self.root / "bin"))
        def run(**extra):
            return subprocess.run(["/bin/sh", str(script)], env=dict(env, **extra), text=True, capture_output=True)
        good = run()
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        self.assertIn("MANAGEMENT_HTTPS_OK", good.stdout)
        self.assertIn("-q --noproxy * -k", (self.root / "curl.calls").read_text())
        self.assertIn("HTTPS_REQUEST_FAILED", run(CURL_EXIT="7").stdout)
        self.assertNotEqual(run(CURL_EXIT="7").returncode, 0)
        self.assertIn("HTTPS_RESPONSE_UNEXPECTED", run(CURL_CODE="500").stdout)
        for name in ("lib/libustream-ssl.so", "usr/sbin/px5g", "etc/uhttpd.crt", "etc/uhttpd.key"):
            (self.root / name).unlink()
        self.write("etc/init.d/uhttpd", "#!/bin/sh\nexit 1\n", True)
        # A remote port 443 / non-LISTEN connection must not pass the check.
        self.write("proc/net/tcp", "0: 00000000:1234 00000000:01BB 01\n")
        result = run()
        self.assertEqual(result.returncode, 1)
        for code in ("UHTTPD_NOT_RUNNING", "TLS_LIBRARY_MISSING", "CERT_GENERATOR_MISSING",
                     "CERT_MISSING_OR_EMPTY", "KEY_MISSING_OR_EMPTY", "HTTPS443_IPV4_NOT_LISTENING"):
            self.assertIn("FAIL " + code, result.stdout)
        (self.root / "bin/curl").unlink()
        self.assertIn("TEST_DEPENDENCY_CURL_MISSING", run().stdout)

    def test_native_sysupgrade_keep_list_includes_generated_credentials(self):
        # Execute native backup-list functions against a fixture APK filesystem.
        # The generated credentials are deliberately absent from conffiles_static.
        source = (ROOT / "package/base-files/files/sbin/sysupgrade").read_text()
        functions = source[source.index("list_conffiles() {"):source.index("build_list_of_backup_overlay_files() {")]
        for prefix in ("/etc/", "/lib/", "/usr/"):
            functions = functions.replace(prefix, str(self.root) + prefix)
        self.write("lib/apk/packages/uhttpd.conffiles_static", "")
        self.write("etc/sysupgrade.conf", "")
        for name in ("etc/uhttpd.crt", "etc/uhttpd.key"):
            self.write(name, "fixture")
        keep = (ROOT / "package/network/services/uhttpd/files/uhttpd.upgrade").read_text()
        self.write("lib/upgrade/keep.d/uhttpd", keep.replace("/etc/", str(self.root) + "/etc/"))
        harness = self.write("backup-list.sh", functions + '\nbuild_list_of_backup_config_files "$1"\n')
        output = self.root / "backup-list"
        subprocess.run(["sh", str(harness), str(output)], check=True)
        self.assertEqual(set(output.read_text().splitlines()),
                         {str(self.root / "etc/uhttpd.crt"), str(self.root / "etc/uhttpd.key")})


if __name__ == "__main__":
    unittest.main()
