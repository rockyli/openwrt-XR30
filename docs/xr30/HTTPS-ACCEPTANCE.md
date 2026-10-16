# XR30 HTTPS release acceptance

Status for this change: **hardware testing pending**. Local regression tests and
CI image checks are not evidence of a completed flash, boot or upgrade test.
Do not mark a release accepted solely because `uhttpd status` says running or
`VALIDATION_OK.txt` exists. Retain this completed matrix with each release's
source/feed revisions, config and image SHA256, using sanitized results.

## Cause and native behavior

The reported affected image had a TLS runtime and HTTPS configuration but no
certificate, private key or px5g. Installing `px5g-mbedtls` and restarting
uhttpd generated credentials and restored port 443. Earlier upgrades may have
retained certificates from official firmware; that history is unconfirmed.

Source checked in this repository:

- `config/xr30.config` selected LuCI without an explicit certificate generator.
  The seed generator deliberately discards the official installed-package list.
- `package/network/services/uhttpd/files/uhttpd.init` uses px5g (or an openssl
  executable fallback) when either configured credential is missing or empty.
  It adds TLS listeners only when the library and both credential files exist.
  A nonempty existing pair is retained; invalid/expired nonempty credentials
  are not automatically repaired by this mechanism.
- `include/package-pack.mk` only adds files present at build time to APK's
  `conffiles_static`; `package/base-files/files/sbin/sysupgrade` reads that list
  and the native `keep.d`/`sysupgrade.conf` lists. Merely declaring generated
  credentials as package conffiles does not cover this APK path.

The fix selects native HTTPS dependencies and adds default credentials to
uhttpd's `keep.d` list. It does not change the init logic, UCI defaults, network
rules, OpenClash, Tailscale, Sidecar or TSGuard. The generator is not resident.
No shared certificate/private key belongs in firmware or public test artifacts.

## Required path matrix

Use an intended test device with a verified recovery path. Do not rerun the
original bootloader/GPT migration installer for normal sysupgrade testing.
Use an exact candidate image, verify SHA256 and run `sysupgrade -T` before each
upgrade. The following operations are manual; no test script flashes a device.

| Source → candidate | Keep settings | Expected credentials | Result |
| --- | --- | --- | --- |
| Clean install directly into candidate, without official-system initialization | No | New unique pair generated at first normal boot | PENDING |
| Official firmware → candidate | Yes | Existing pair retained if included in source backup list | PENDING |
| Official firmware → candidate | No | New pair generated | PENDING |
| Previous XR30 firmware → candidate | Yes | Existing pair retained if included in source backup list | PENDING |
| Previous XR30 firmware → candidate | No | New pair generated | PENDING |
| Fixed candidate → subsequent fixed build | Yes | Existing pair retained by native keep list | PENDING |

For every row: record source/destination commit, image SHA256, retention choice,
first-boot health, LAN access, reboot health and credential retained/regenerated
result. Check `ubus call system board` reports the intended build and squashfs;
initramfs recovery is not a persistent-system acceptance result. Perform the
initial checks **before** installing Sidecar or other deployment components.

## Preserve settings: check the source before upgrading

This change cannot retroactively fix an older system's backup selection. On the
source device, inspect (do not publish the full list or credential hashes):

```sh
sysupgrade -l | grep -E '^/etc/uhttpd\.(crt|key)$'
```

Both default paths must appear if they exist and retention is intended. If
either is absent, add explicit entries on that source system before upgrading:

```sh
touch /etc/sysupgrade.conf
for path in /etc/uhttpd.crt /etc/uhttpd.key; do
    grep -qxF "$path" /etc/sysupgrade.conf || printf '%s\n' "$path" >> /etc/sysupgrade.conf
done
sysupgrade -l | grep -E '^/etc/uhttpd\.(crt|key)$'
```

For custom UCI certificate/key paths, inspect `uci get uhttpd.main.cert` and
`uci get uhttpd.main.key`, and add those actual paths instead. Keep credentials
and their private backup outside this public repository. Compare local SHA256
of the two files before/after retained upgrades and reboots; record only
"unchanged" in public results. With settings discarded, do not restore an old
configuration backup: the pair should be newly generated. A retained config
that intentionally disables HTTPS is retained too; this fix does not override it.

## Health and access checks

The build artifact includes `check-management-https.sh`. Copy it to `/tmp` on
the router and run it after first boot and again after reboot:

```sh
sh /tmp/check-management-https.sh
```

It is read-only and returns nonzero on failure, including a missing test tool.
It checks the native `main` instance, default 80/443 ports, IPv4 and configured
IPv6 listeners, and a loopback HTTPS HEAD request with connection/total timeout.
It reports distinct causes for stopped uhttpd, missing TLS library, missing
generator, missing/empty certificate or key, absent listener, and failed HTTP
response. `2xx` and `3xx` responses pass; error responses fail. Listening sockets
are read from `/proc/net/tcp*`, so `ss` and diagnostic kernel modules are not
required. `curl` is required only on the test device; if absent, record the
initial certificate/listener state first, then install **only** `curl` from the
matching official feed and rerun. Do not install px5g to make a candidate pass.

For default-image acceptance, both IPv4 and IPv6 port checks must PASS; an IPv6
SKIP is not a pass. A loopback success does not establish external reachability
or prove that the LuCI login page renders correctly. From a LAN client, open the
HTTPS LuCI page (fresh/private browser window) and run:

```sh
curl -q --noproxy '*' -kI --connect-timeout 5 --max-time 15 https://192.168.10.1/
```

Use the actual LAN address when settings were retained. Confirm HTTP/80 too.
A self-signed-certificate warning is expected and differs from connection
refused. `-k` tests TLS service availability, not certificate trust/identity.

After baseline acceptance, deploy the usual OpenClash/Tailscale/Sidecar setup.
Repeat the health and LAN checks, and access HTTPS from a **different Tailnet
client** using the router's actual Tailnet IP, subject to the intended firewall
and Tailnet access policy. Do not open WAN management ports for this test.
Verify the existing application functions still work and repeat after reboot.
An optional `https://.../` argument to the script tests an additional URL from
the router; it does not replace the external client/firewall test.

## Missing credential recovery and preservation

On a disposable test installation only, securely save both files outside the
public repository, then test: both absent, certificate absent, key absent, and
one file empty. Restart native uhttpd after each case. It must regenerate a
usable pair and pass the health check without installing packages or Sidecar.
Removing either half can replace **both** files; this is native behavior.

With a valid nonempty pair, restart uhttpd and reboot normally; neither file's
hash should change. Confirm the same for retained sysupgrade using the matrix
above. Missing/corrupt/expired credentials are different cases: the init script
does not validate and replace a nonempty pair, so record HTTPS request errors
and investigate without silently rotating user-provided credentials.

## Release gate

- [ ] Exact candidate config and installed-package manifest include the HTTPS dependencies.
- [ ] `https-image-check.log` passes; firmware contains no generated credentials.
- [ ] All required path-matrix rows have real-device results.
- [ ] Fresh first boot and reboot pass HTTP/HTTPS IPv4 and IPv6 checks.
- [ ] LAN browser and HTTPS response verified independently of Sidecar.
- [ ] External Tailnet HTTPS access and application regression checks pass.
- [ ] Missing-file recovery and retained-pair tests pass.
- [ ] Source backup lists and retained/discarded upgrade results are recorded.
- [ ] Review sanitized results before release; never upload keys or private backups.

The workflow leaves `HTTPS_HARDWARE_PENDING.txt` in every candidate artifact.
Only completed device evidence can close this manual release gate; CI must not
replace pending hardware results with a simulated pass.
