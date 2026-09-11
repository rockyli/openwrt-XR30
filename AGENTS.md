# XR30 repository instructions

## Scope and upstream

- This is a public OpenWrt derivative for CMCC XR30 / RAX3000Z.
- Keep `main` and `openwrt-25.12` as unmodified upstream tracking branches.
- Make project changes on `xr30-25.12` or a feature branch based on it.
- Initial base: OpenWrt `v25.12.5`, commit `f0a60eee2fe051741c643ea6118718aae1ef17fb`.
- Merge reviewed upstream updates; never force-reset the XR30 branch.
- Keep device support, package selection, defaults, CI and documentation in separate commits when practical.
- Runtime compatibility and bootloader FIT configuration names must be verified before renaming a device profile. A display-name change is not proof of full hardware compatibility.

## Privacy and publication

- Never commit device dumps, stock firmware backups, Factory/EEPROM data, calibration blobs, device-specific hashes, serial numbers, real MAC addresses, or private network details.
- Never commit passwords, private keys, API tokens, VPN enrollment keys, actual `.env` files, or unsanitized router configs/logs/screenshots.
- Use placeholders in public examples. Set device credentials locally after installation.
- Use GitHub Secrets only for credentials required by CI. Do not echo secrets, include them in build inputs that enter firmware, or upload them as artifacts.
- Inspect the exact staged diff and new files before every commit. Ignore rules are an aid, not a security boundary; they do not remove tracked files.
- Review release assets, firmware defaults and logs separately before publishing. An automated scan does not establish the absence of secrets.
- Do not copy prior per-device flashing scripts or private documentation wholesale into this repository; first remove identifiers, hashes and credentials and redesign device-specific checks.
- If a secret is accidentally published, stop publishing and notify the owner; credential rotation and history cleanup require separate handling. Deleting the latest file alone is insufficient.

## Validation

- Do not claim hardware validation based only on a successful build.
- Preserve upstream licenses and authorship.
- Record exact OpenWrt and feed revisions, configuration and image hashes for each release.
- No automatic firmware release or device flashing from upstream synchronization jobs.
