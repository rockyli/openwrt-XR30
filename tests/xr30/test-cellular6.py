"""Exercise XR30's shipped scripts using a host ucode and isolated OpenWrt fixtures."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "package/network/config/xr30-ml307r/files"
DHCP = ROOT / "package/network/ipv6/odhcp6c/files"
UCODE = os.environ.get("UCODE", "ucode")


class Cellular6(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.net = self.root / "net"
        self.net.mkdir()
        helper = (FILES / "cellular6.uc").read_text()
        for module in ("uci", "fs", "ubus"):
            helper = helper.replace(f"from '{module}'", f"from './{module}.uc'")
        self.helper = self.root / "xr30-cellular6"
        self.helper.write_text(helper)
        (self.root / "fs.uc").write_text("""
export function open() { return { lock: () => true }; };
export function dirname() { return getenv('FIXTURES'); };
""")
        (self.root / "uci.uc").write_text("""
export function cursor() {
    let result = {};
    return {
        get_all: (name) => json(getenv(name)),
        set: (file, name, key, value) => {
            if (file != 'network' || name != 'cellular6') die('unexpected UCI edit');
            result[key] = value;
            return true;
        },
        save: () => { print(result); return true; }
    };
};
""")
        (self.root / "ubus.uc").write_text("""
export function connect() {
    return { call: (object, method, args) => {
        if (object == 'network.interface' && method == 'dump')
            return { interface: json(getenv('live')) };
        if (object != 'network' || method != 'add_dynamic') die('unexpected ubus call');
        print(args);
        return {};
    }};
};
""")
        wrapper = self.root / "xr30-name-ml307r"
        wrapper.write_text('#!/bin/sh\n'
                           'if [ "$1" = --matches ]; then set -- "$1" "$FIXTURES/net/${2##*/}"; fi\n'
                           'exec sh "$MATCHER" "$@"\n')
        wrapper.chmod(0o755)
        self.network = {
            "cellular": {".type": "interface", "proto": "dhcp", "device": "cell0"},
            "wan6": {".type": "interface", "proto": "dhcpv6", "device": "@wan"},
            "wan": {".type": "interface", "proto": "dhcp", "device": "eth1"},
        }
        self.zone = {".type": "zone", "name": "wan", "input": "REJECT",
                     "network": ["wan", "wan6", "cellular"]}
        self.firewall = {"uplink": self.zone}
        self.live = [{"interface": "cellular", "proto": "dhcp", "available": True,
                      "autostart": True, "device": "cell0"}]

    def modem(self, name, vid, pid, driver, product):
        # Match sysfs through a hub: the NIC links to the USB function, whose
        # parent carries idVendor, idProduct and the product string.
        device = self.root / "usb1/1-1/1-1.2/1-1.2:1.0"
        device.mkdir(parents=True, exist_ok=True)
        nic = self.net / name
        nic.mkdir(exist_ok=True)
        if not (nic / "device").exists():
            (nic / "device").symlink_to(device)
        for key, value in [("product", product), ("idVendor", vid), ("idProduct", pid)]:
            (device.parent / key).write_text(value + "\n")
        link = device / "driver"
        link.unlink(missing_ok=True)
        link.symlink_to("/drivers/" + driver)

    def evaluate(self, *args):
        env = dict(os.environ, FIXTURES=str(self.root), MATCHER=str(FILES / "name-device"),
                   network=json.dumps(self.network), firewall=json.dumps(self.firewall),
                   live=json.dumps(self.live))
        out = subprocess.check_output([UCODE, self.helper, *args], text=True, env=env)
        return json.loads(out) if out else None

    def test_factory_can_run_without_a_modem(self):
        result = self.evaluate("factory")
        self.assertEqual((result["device"], result["proto"], result["zone"]),
                         ("cell0", "dhcpv6", "wan"))
        self.assertEqual((result["reqaddress"], result["reqprefix"], result["fakeroutes"]),
                         ("try", "auto", "0"))

    def test_retained_names_replug_and_duplicate_events(self):
        for name, vid, pid, driver, product in [
            ("ml307r0", "2ecc", "3012", "cdc_ether", "ML307R"),
            ("cell0", "18d1", "d001", "rndis_host", "HandsomeMod Device"),
            ("usb0", "18d1", "d001", "rndis_host", "HandsomeMod Device"),
        ]:
            with self.subTest(name=name):
                self.network["cellular"].update(device=name, peerdns="0", metric="200")
                self.live[0]["device"] = name
                self.assertIsNone(self.evaluate())
                self.modem(name, vid, pid, driver, product)
                created = self.evaluate()
                self.assertEqual((created["name"], created["device"], created["peerdns"],
                                  created["metric"]), ("cellular6", name, False, 200))
                self.live.append(dict(created, interface="cellular6"))
                self.assertIsNone(self.evaluate())
                self.live.pop()
                self.assertEqual(self.evaluate(), created)

    def test_existing_configs_and_dynamic_owners(self):
        self.modem("cell0", "2ecc", "3012", "cdc_ether", "ML307R")
        for section in [{"proto": "dhcpv6", "device": "@cellular", "auto": "0"},
                        {"proto": "dhcpv6", "device": "cell0"},
                        {"proto": "dhcpv6", "device": "@unknown"}]:
            self.network["custom"] = dict(section, **{".type": "interface"})
            self.assertIsNone(self.evaluate())
        del self.network["custom"]
        self.live.append({"interface": "custom_6", "proto": "dhcpv6", "l3_device": "cell0"})
        self.assertIsNone(self.evaluate())
        self.live.pop()
        self.network["cellular6"] = {".type": "interface", "proto": "static"}
        self.assertIsNone(self.evaluate())
        del self.network["cellular6"]
        self.network["cellular"]["auto"] = "0"
        self.assertIsNone(self.evaluate())

    def test_usb_identity_at_boot_hotplug_and_ipv6_setup(self):
        # Source the installed entry points against fixture paths. Record rename
        # requests instead of changing host links or calling the host's UCI.
        for name, command in {
            "uci": '[ "$*" = "-q get network.cellular.device" ] && echo "$TARGET"',
            "ip": 'echo "$*"',
        }.items():
            stub = self.root / name
            stub.write_text("#!/bin/sh\n" + command + "\n")
            stub.chmod(0o755)
        for name in ("init", "hotplug"):
            script = (FILES / name).read_text().replace("/sys/class/net", str(self.net))
            script = script.replace("/usr/libexec", str(self.root))
            script = script.replace("/etc/xr30-cellular6-auto", str(self.root / "auto"))
            (self.root / name).write_text(script)

        self.network["cellular"]["device"] = self.live[0]["device"] = "usb0"
        for vid, pid, driver, label, accepted in [
            ("18d1", "d001", "cdc_ether", "HandsomeMod Device", True),
            ("18d1", "d001", "rndis_host", "HandsomeMod Device", True),
            ("2ecc", "3012", "cdc_ether", "ML307R", True),
            ("1234", "5678", "cdc_ether", "USB Ethernet", False),
            ("1234", "d001", "cdc_ether", "HandsomeMod Device", False),
            ("18d1", "d002", "cdc_ether", "HandsomeMod Device", False),
            ("18d1", "d001", "cdc_ether", "HandsomeMod Device ", False),
            ("18d1", "d001", "cdc_ncm", "HandsomeMod Device", False),
            ("2ecc", "3012", "rndis_host", "ML307R", False),
        ]:
            with self.subTest(vid=vid, pid=pid, driver=driver, label=label):
                self.modem("usb0", vid, pid, driver, label)
                self.assertEqual(self.evaluate() is not None, accepted)
                for target in ("ml307r0", "cell0"):
                    env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                               TARGET=target, ACTION="add", DEVICENAME="usb0", MATCHER=str(FILES / "name-device"))
                    for entry in ['. ./init && start', '. ./hotplug']:
                        with self.subTest(target=target, entry=entry):
                            out = subprocess.check_output(["sh", "-c", entry], cwd=self.root, env=env, text=True)
                            self.assertEqual(out.strip(), f"link set dev usb0 name {target}" if accepted else "")

    def test_unrelated_hardware_and_conflicting_firewall(self):
        self.modem("cell0", "18d1", "d001", "rndis_host", "another device")
        self.assertIsNone(self.evaluate())
        self.modem("cell0", "18d1", "d001", "rndis_host", "HandsomeMod Device")
        self.firewall["other"] = dict(self.zone, name="other")
        self.assertIsNone(self.evaluate())
        del self.firewall["other"]
        self.zone["input"] = "ACCEPT"
        self.assertIsNone(self.evaluate())

    def test_ra_preference_pd_and_withdrawal(self):
        # Run the real lease script with recording netifd callbacks.
        src = (DHCP / "dhcpv6.script").read_text()
        src = "\n".join(s for s in src.splitlines() if not s.startswith(". /lib/"))
        src = src.replace("/proc/sys", str(self.root / "proc")).replace("/etc/odhcp6c", str(self.root / "user"))
        hop = self.root / "proc/net/ipv6/conf/cell0/hop_limit"
        hop.parent.mkdir(parents=True)
        hop.write_text("64\n")
        funcs = ["proto_init_update", "proto_add_ipv6_address", "proto_add_ipv6_prefix",
                 "proto_add_ipv6_route", "proto_add_data", "proto_close_data", "proto_send_update"]
        prelude = '\n'.join(f'{f}() {{ echo "{f} $*"; }}' for f in funcs)
        script = self.root / "lease.sh"
        script.write_text(prelude + '\nnetwork_generate_iface_iaid() { :; }\n' + src)
        env = dict(INTERFACE="cellular6", DYNAMIC="0", RA_ADDRESSES="2001:db8:1::1/64,60,120",
                   RA_ROUTES="::/0,fe80::1,120,512 2001:db8:1::/64,,120,256")

        def event(name):
            return subprocess.check_output(["bash", script, "cell0", name], env=env, text=True)

        self.assertIn("proto_add_ipv6_route :: 0 fe80::1 512 120", event("ra-updated"))
        env["RA_DEFAULT_METRIC_OFFSET"] = "4096"
        out = event("ra-updated")
        self.assertIn("proto_add_ipv6_address 2001:db8:1::1", out)
        self.assertIn("proto_add_ipv6_route :: 0 fe80::1 4608 120 2001:db8:1::1/64", out)
        self.assertIn("proto_add_ipv6_route 2001:db8:1:: 64  256 120", out)
        self.assertNotIn("proto_add_ipv6_prefix", out)
        env["PREFIXES"] = "2001:db8:2::/56,60,120"
        out = event("bound")
        self.assertIn("proto_add_ipv6_prefix " + env["PREFIXES"], out)
        self.assertIn("4608 120 2001:db8:2::/56", out)
        self.assertEqual(event("unbound").splitlines(),
                         ["proto_init_update * 0", "proto_send_update cellular6"])


if __name__ == "__main__":
    unittest.main()
