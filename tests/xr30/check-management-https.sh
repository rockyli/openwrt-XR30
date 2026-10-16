#!/bin/sh
# Read-only device check. Run after normal boot; no restart or configuration edits.
# curl is a test dependency, not a new firmware/runtime dependency.

failed=0
pass() { printf 'PASS %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*"; failed=1; }

case "${1:-}" in
	--help)
		echo "Usage: sh $0 [https://LAN-IP/ [https://TAILNET-IP/]]"
		echo 'Checks native uhttpd main, default ports 80/443, and optional HTTPS URLs.'
		exit 0
		;;
esac
for url in "$@"; do
	case "$url" in https://*) ;; *) echo 'Only https:// URLs are accepted.' >&2; exit 2 ;; esac
done

if /etc/init.d/uhttpd status >/dev/null 2>&1; then
	pass UHTTPD_RUNNING
else
	fail UHTTPD_NOT_RUNNING
fi

if [ -s /lib/libustream-ssl.so ]; then
	pass TLS_LIBRARY_PRESENT
else
	fail TLS_LIBRARY_MISSING
fi

# These are the exact executable paths used by the native init script.
if [ -x /usr/sbin/px5g ]; then
	pass CERT_GENERATOR_PX5G
elif [ -x /usr/bin/openssl ]; then
	fail PX5G_MISSING_OPENSSL_FALLBACK_AVAILABLE
else
	fail CERT_GENERATOR_MISSING
fi

if ! command -v uci >/dev/null 2>&1; then
	fail UCI_MISSING
	cert=/etc/uhttpd.crt
	key=/etc/uhttpd.key
else
	cert=$(uci -q get uhttpd.main.cert)
	key=$(uci -q get uhttpd.main.key)
	cert=${cert:-/etc/uhttpd.crt}
	key=${key:-/etc/uhttpd.key}
	if [ -n "$(uci -q get uhttpd.main.listen_https)" ]; then
		pass HTTPS_CONFIGURED
	else
		fail HTTPS_LISTEN_CONFIG_MISSING
	fi
fi
if [ -s "$cert" ] && [ -r "$cert" ]; then pass CERT_PRESENT; else fail CERT_MISSING_OR_EMPTY; fi
if [ -s "$key" ] && [ -r "$key" ]; then pass KEY_PRESENT; else fail KEY_MISSING_OR_EMPTY; fi

# /proc avoids requiring ss or kmod-inet-diag just for this check. Match the
# local port and TCP LISTEN state, not established or remote-port connections.
check_listener() {
	local table="$1" port="$2" label="$3"
	if [ ! -r "$table" ]; then
		fail "${label}_UNOBSERVABLE"
	elif awk -v port="$port" '
		$4 == "0A" { split($2, address, ":"); if (toupper(address[2]) == port) found=1 }
		END { exit !found }
	' "$table"; then
		pass "${label}_LISTENING"
	else
		fail "${label}_NOT_LISTENING"
	fi
}
check_listener /proc/net/tcp 0050 HTTP80_IPV4
check_listener /proc/net/tcp 01BB HTTPS443_IPV4
# Default XR30 configuration enables IPv6. An intentionally disabled listener
# is reported as skipped, and is not evidence of passing the default-image test.
if uci -q get uhttpd.main.listen_https 2>/dev/null | grep -q '\[::\]:443'; then
	check_listener /proc/net/tcp6 01BB HTTPS443_IPV6
else
	echo 'SKIP HTTPS443_IPV6_NOT_CONFIGURED'
fi
if uci -q get uhttpd.main.listen_http 2>/dev/null | grep -q '\[::\]:80'; then
	check_listener /proc/net/tcp6 0050 HTTP80_IPV6
fi

check_response() {
	local url="$1" code rc
	# -q must come first: ignore curlrc. Bypass proxies and allow the device's
	# self-signed certificate; this probes availability, not CA trust or identity.
	code=$(curl -q --noproxy '*' -k -sS -I -o /dev/null -w '%{http_code}' \
		--connect-timeout 5 --max-time 15 "$url")
	rc=$?
	if [ "$rc" -ne 0 ]; then
		fail "HTTPS_REQUEST_FAILED curl_exit=$rc url=$url"
	else
		case "$code" in
			2[0-9][0-9]|3[0-9][0-9]) pass "HTTPS_RESPONSE code=$code url=$url" ;;
			*) fail "HTTPS_RESPONSE_UNEXPECTED code=$code url=$url" ;;
		esac
	fi
}
if command -v curl >/dev/null 2>&1; then
	check_response https://127.0.0.1/
	for url in "$@"; do check_response "$url"; done
else
	fail TEST_DEPENDENCY_CURL_MISSING
fi

if [ "$failed" -ne 0 ]; then
	echo 'MANAGEMENT_HTTPS_FAILED'
	exit 1
fi
echo 'MANAGEMENT_HTTPS_OK (external LAN/Tailnet access still requires client testing)'
