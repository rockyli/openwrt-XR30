#!/usr/bin/ucode
'use strict';
import * as uci from 'uci';
import * as ubus from 'ubus';
import { open, dirname } from 'fs';

// Net and iface hotplug events may arrive concurrently.
const lock = open('/var/run/xr30-cellular6.lock', 'a');
if (!lock || !lock.lock('x'))
	die('Cannot lock XR30 cellular6 setup');

const factory = ARGV[0] == 'factory';
const ctx = uci.cursor();
const network = ctx.get_all('network');
const firewall = ctx.get_all('firewall');
if (!network || !firewall)
	die('Cannot read XR30 network and firewall configuration');

const parent = network.cellular;
const dev = parent?.device ?? parent?.ifname;
function enabled(value) {
	return index(['1', 'on', 'yes', 'true', 'enabled'], lc('' + value)) >= 0;
}
if (network.cellular6) {
	if (network.cellular6.proto != 'dhcpv6')
		warn('XR30 cellular6: existing section owns this name\n');
	exit(0);
}
if (!dev || parent.proto != 'dhcp' ||
    (parent.auto != null && !enabled(parent.auto)) ||
    (parent.ipv6 != null && !enabled(parent.ipv6)))
	exit(0);

function words(value) {
	return type(value) == 'array' ? value : split(value ?? '', /[ \t]+/);
}

// Resolve @interface chains, including retained aliases which are down.
function carrier(device) {
	let seen = {};
	while (type(device) == 'string' && substr(device, 0, 1) == '@') {
		if (seen[device])
			return null;
		seen[device] = true;
		let section = network[substr(device, 1)];
		device = section?.device ?? section?.ifname;
	}
	return device;
}

function preserves_client(section) {
	if (section.proto != 'dhcpv6')
		return false;
	let configured = network[section.interface];
	let device = carrier(section.l3_device ?? section.device ?? section.ifname ??
	                     configured?.device ?? configured?.ifname);
	// An unresolved DHCPv6 owner may be using this bearer.
	if (!device)
		warn('XR30 cellular6: cannot resolve device of existing DHCPv6 client\n');
	return !device || device == dev;
}

for (let name, s in network) {
	if (s['.type'] == 'interface' && preserves_client(s))
		exit(0);
	if (s['.type'] == 'device' && s.name == dev && s.ipv6 != null && !enabled(s.ipv6))
		exit(0);
	if (s['.type'] == 'interface' && name != 'cellular' &&
	    carrier(s.device ?? s.ifname) == dev && (s.ipv6 == 'auto' || enabled(s.ipv6)))
		exit(0);
}

let bus, liveZone;
if (!factory) {
	// Verify custom interface names too, without adopting an unrelated NIC.
	if (!match(dev, /^[a-zA-Z0-9_.-]{1,15}$/))
		exit(0);
	let matcher = dirname(sourcepath()) + '/xr30-name-ml307r';
	if (system([matcher, '--matches', '/sys/class/net/' + dev]) != 0)
		exit(0);
	bus = ubus.connect();
	let interfaces = bus?.call('network.interface', 'dump')?.interface;
	if (type(interfaces) != 'array')
		exit(0);
	let owner = false;
	for (let s in interfaces) {
		if (s.interface == 'cellular6' || preserves_client(s))
			exit(0);
		if (s.interface == 'cellular' && s.available && s.autostart &&
		    (s.l3_device ?? s.device ?? dev) == dev) {
			owner = true;
			liveZone = s.data?.zone;
		}
	}
	if (!owner)
		exit(0);
}

// Use the existing uplink policy. Never guess between zones or add allow rules.
let zones = [], reservations = [], defaultInput;
let explicitZone = liveZone ?? parent.zone;
for (let name, z in firewall) {
	if (z['.type'] == 'defaults')
		defaultInput = z.input;
	if (z['.type'] != 'zone')
		continue;
	let nets = words(z.network);
	if (index(nets, 'cellular') >= 0 || (explicitZone && z.name == explicitZone))
		push(zones, z);
	if (index(nets, 'cellular6') >= 0)
		push(reservations, z.name);
}
let zone = zones[0];
if (length(zones) != 1 || !zone.name || zone.name == 'lan' ||
    uc(zone.input ?? defaultInput ?? 'DROP') == 'ACCEPT' ||
    zone.family == 'ipv4' || (length(reservations) && join(' ', reservations) != zone.name)) {
	warn('XR30 cellular6: unresolved or conflicting uplink firewall zone\n');
	exit(0);
}

let opts = { proto: 'dhcpv6', device: dev, reqaddress: 'try', reqprefix: 'auto',
             fakeroutes: '0', ra_default_metric_offset: '4096',
             metric: parent.metric ?? '100', zone: zone.name };
for (let key in ['defaultroute', 'peerdns', 'dns_metric', 'delegate'])
	if (parent[key] != null)
		opts[key] = parent[key];

if (factory) {
	if (!ctx.set('network', 'cellular6', 'interface'))
		die('Cannot create network.cellular6');
	for (let key, value in opts)
		if (!ctx.set('network', 'cellular6', key, value))
			die('Cannot configure cellular6 option ' + key);
	// The boot service commits staged defaults. fw4 reads the netifd zone.
	if (!ctx.save('network'))
		die('Cannot stage network.cellular6');
} else {
	opts.name = 'cellular6';
	// add_dynamic consumes typed ubus fields; UCI stores the same values as strings.
	opts.metric = int(opts.metric);
	opts.ra_default_metric_offset = int(opts.ra_default_metric_offset);
	if (opts.dns_metric != null)
		opts.dns_metric = int(opts.dns_metric);
	for (let key in ['defaultroute', 'peerdns', 'delegate', 'fakeroutes'])
		if (opts[key] != null)
			opts[key] = enabled(opts[key]);
	if (bus.call('network', 'add_dynamic', opts) == null && bus.error())
		die('Cannot register dynamic cellular6 with netifd');
}
