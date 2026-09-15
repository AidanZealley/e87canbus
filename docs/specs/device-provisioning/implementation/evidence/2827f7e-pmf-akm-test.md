# Candidate 2827f7e PMF/AKM discrimination test

Date: 2026-09-15  
Candidate: `2827f7eaa2a69f5c1daf26910c4fe813a974b8e3`  
Deployment profile: `bench`  
Installation ID: `jv4xu4p3ip2r6ngwxlbgv3nwpx6wx7yeeufe5kerapegyej44c4q`

## Result

**The cause of the status-16 failure is radio interference from the console's DSI touchscreen.** It is not the SHA256 AKM, PMF, firmware PSK offload, regulatory domain, the Debian firmware swap or the kernel.

With the display attached, the console's 2.4 GHz reception is impaired. It fails to join the coordinator on channel 1 (and on 36 and 149), is intermittent on channel 6, and joins reliably only on channel 11. With the DSI ribbon disconnected, and nothing else changed, the console joins the coordinator on channel 1 with the unmodified production security profile every time. The untouched provisioned keyfiles then connect by themselves: `wpa_state=COMPLETED`, `10.42.0.2`, and ping to `10.42.0.1` succeeds.

This is the handoff's "console still fails" outcome for the AKM question. The SHA256 AKM is ruled out because the console fails identically forced to plain WPA2-PSK (`akm=0xfac02`) with PMF disabled, with firmware PSK offload disabled, and against an open AP. Driver debug shows what brcmfmac hides behind status 16: the firmware's own join reports `SET_SSID` `status 1` (`BRCMF_E_STATUS_FAIL`).

The cards were modified at runtime only and have been restored (see [Restore](#restore)). They should be treated as diagnostic. Final gate evidence must come from freshly provisioned clean cards.

## Test setup

Both cards are the ones provisioned for [`2827f7e-physical-gate-report.md`](2827f7e-physical-gate-report.md):

- Coordinator `e87-coordinator-1069df5e6c91`, AP BSSID `88:a2:9e:ff:6d:38`, host key `SHA256:wEoKt/g0SUA9WS1NAvw61dLUKTKynx9zWpNhWqgG9io`
- Console `e87-console-ef27d0966bdd`, Wi-Fi MAC `d8:3a:dd:3c:54:f6`, host key `SHA256:beb1A7dMnqYI//vT7LkQWbRgXpQXJjs9GFMiCBuFIv8`

Access was over Ethernet as `e87-admin` with the installation recovery key. Only one cable was available at first, so the coordinator's `pmf=1` change was scheduled as a one-shot `systemd-run` job that fired 2 minutes after its cable was unplugged. The cable then moved to the console. Later the coordinator was moved to the home router and both devices were reachable at the same time for the extended experiments.

Physical placement changed during the session. For the baseline and steps 2 to 3 the Pis sat side by side on the bench, and the console saw the coordinator at about -22 dBm. For the extended experiments the coordinator sat by the router, and the console saw it at -55 to -69 dBm.

The only other 2.4 GHz network visible was the home network on channel 2 (2417 MHz) at -42 dBm. On 5 GHz, the home network and two neighbours share channel 36 (5180 MHz). The Mac reports the home 5 GHz network as 80 MHz wide with country code GB.

## Step 0: profile backups

```text
$ sudo sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection /root/e87canbus-wifi.nmconnection.bak
```

Coordinator:

```text
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /root/e87canbus-wifi.nmconnection.bak
-rw------- 1 root root  355 Sep 14 18:55 e87canbus-wifi.nmconnection
```

Console:

```text
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /root/e87canbus-wifi.nmconnection.bak
-rw------- 1 root root  363 Sep 14 19:03 e87canbus-wifi.nmconnection
```

Both profiles contained the generator's `[wifi-security]` section, with the PSK omitted here:

```text
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
```

## Step 1: baseline

Both devices returned:

```text
$ uname -r
6.18.39+rpt-rpi-v8

$ dpkg-query -W firmware-brcm80211
firmware-brcm80211	20250410-2

$ cat /sys/module/brcmfmac/parameters/feature_disable
cat: /sys/module/brcmfmac/parameters/feature_disable: No such file or directory

$ sudo ls /sys/module/brcmfmac/parameters/
alternative_fw_path
debug
roamoff

$ sudo cat /sys/module/brcmfmac/parameters/roamoff
0
```

### `feature_disable` readback

`feature_disable` is not exposed in sysfs on this kernel, so it cannot be read back at runtime. No `brcmfmac` options exist in `/etc/modprobe.d`, `/usr/lib/modprobe.d`, `/lib/modprobe.d` or `/run/modprobe.d`, and none are on the kernel command line, so the running value is the default `0`. The only reliable proof that it applied is the driver's own debug line at load time (see [Firmware PSK offload](#firmware-psk-offload-disabled)).

The Raspberry Pi vendor module on this kernel is `brcmfmac_cyw`, and it holds a reference to `brcmfmac`:

```text
$ lsmod | grep brcm
brcmfmac_cyw           12288  0
brcmfmac              376832  1 brcmfmac_cyw
brcmutil               24576  1 brcmfmac

$ sudo modprobe -r brcmfmac
modprobe: FATAL: Module brcmfmac is in use.
```

When unload fails this way, a following `modprobe brcmfmac feature_disable=0x282000` does nothing, because the module is already loaded, and it prints no error. The first reload attempt in this session hit exactly that. `modprobe -r brcmfmac_cyw brcmfmac` is required. The earlier report's reload experiment may not have applied its options for the same reason. The commands used then were not recorded, so this cannot be confirmed.

### Coordinator AP

```text
$ sudo wpa_cli -i wlan0 status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
id=0
mode=AP
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.1
p2p_device_address=ca:44:98:9e:9d:b5
address=88:a2:9e:ff:6d:38
uuid=4272adf6-5784-5a69-b8bf-a840cb8804bb
```

### AP as seen by the console

```text
$ sudo wpa_cli -i wlan0 bss 88:a2:9e:ff:6d:38
id=0
bssid=88:a2:9e:ff:6d:38
freq=2412
beacon_int=100
capabilities=0x1511
qual=0
noise=-95
level=-22
tsf=0000000000000000
age=1
ie=001665383763616e6275732d6a7634787534703369703272010882848b962430486c0301010504000200000706555320010b1e200100230212002a010032040c12186030140100000fac040100000fac040100000fac06cc002d1a210017ff000000000000000000000000000000000000000000003d16010811000000000000000000000000000000000000004a0e14000a002c01c8001400050019007f080500080000000040dd290050f204104a00011010440001021049000600372a0001201011000120105400080000000000000000dd090010180200001c0000dd180050f2020101800003a4000027a4000042435e0062322f00
flags=[WPA2-PSK-SHA256-CCMP][WPS][ESS]
ssid=e87canbus-jv4xu4p3ip2r
wps_state=configured
wps_primary_device_type=0-00000000-0
wps_device_name= 
snr=73
est_throughput=65000
update_idx=18
```

This `wpa_cli` build prints no `[MFP]` flag. The RSN IE (`30 14 …`) lists AKM `00-0f-ac:6` only, with RSN capabilities `0x00cc`, meaning MFP capable and MFP required. The beacon also carries a `US` country IE (`07 06 55 53 20 01 0b 1e`, channels 1 to 11) while both Pis run with `ieee80211_regdom=00`.

## Step 2: both sides at `pmf=1`

### Coordinator

The scheduled job's log:

```text
end0 carrier lost: 2026-09-15T07:21:28+00:00
flip start: 2026-09-15T07:23:28+00:00
$ nmcli connection modify e87canbus-coordinator-wifi 802-11-wireless-security.pmf 1
$ nmcli connection up e87canbus-coordinator-wifi
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/4)
$ wpa_cli -i wlan0 status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
id=0
mode=AP
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=UNKNOWN
wpa_state=COMPLETED
ip_address=10.42.0.1
p2p_device_address=ca:44:98:9e:9d:b5
address=88:a2:9e:ff:6d:38
uuid=4272adf6-5784-5a69-b8bf-a840cb8804bb
$ sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
2a8cb799e4951f6c5818f07c87df282cb351604d407624ea0d365b85ead4b215  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
flip done: 2026-09-15T07:23:35+00:00
```

As the handoff expected, nmcli rewrote and normalised the keyfile (`uuid`, `timestamp`, `;`-terminated lists, `[proxy]`), which changed its hash.

**Setting `pmf=1` in NetworkManager's AP mode does not produce a plain-PSK-only AP.** `key_mgmt` reads `UNKNOWN` rather than `WPA2-PSK`, and the console's scan shows the AP now advertising both AKMs with MFP off:

```text
2026-09-15T07:23:30+00:00 age=2 flags=[WPA2-PSK-SHA256-CCMP][WPS][ESS] 
2026-09-15T07:23:36+00:00 age=2 flags=[WPA2-PSK+PSK-SHA256-CCMP][WPS][ESS] 
```

```text
ie=…30180100000fac040100000fac040200000fac02000fac060c00…
flags=[WPA2-PSK+PSK-SHA256-CCMP][WPS][ESS]
```

The RSN IE now lists two AKMs, `00-0f-ac:2` and `00-0f-ac:6`, with RSN capabilities `0x000c` (MFP neither capable nor required). The handoff's gate ("confirm `key_mgmt` reads `WPA2-PSK`") therefore cannot be met through NM. Instead of the AP-side condition, the discriminating variable was controlled on the station side, as described below.

### Console attempt through NetworkManager (`pmf=1`)

```text
$ sudo nmcli connection modify e87canbus-console-wifi 802-11-wireless-security.pmf 1
$ sudo wpa_cli -i wlan0 bss 88:a2:9e:ff:6d:38 | grep -E "^(bssid|freq|level|flags|ssid)="
bssid=88:a2:9e:ff:6d:38
freq=2412
level=-26
flags=[WPA2-PSK+PSK-SHA256-CCMP][WPS][ESS]
ssid=e87canbus-jv4xu4p3ip2r
```

NetworkManager configured the station with `ieee80211w=0` but still offered SHA256:

```text
NetworkManager[479]: <info>  [1789457154.0672] Config: added 'key_mgmt' value 'WPA-PSK WPA-PSK-SHA256 FT-PSK'
NetworkManager[479]: <info>  [1789457154.0674] Config: added 'ieee80211w' value '0'
```

With wpa_supplicant debug logging enabled, the station chose SHA256 against the dual-AKM AP and failed:

```text
wpa_supplicant[482]: wlan0: WPA: using KEY_MGMT PSK with SHA256
wpa_supplicant[482]: wlan0: Trying to associate with SSID 'e87canbus-jv4xu4p3ip2r'
wpa_supplicant[482]: nl80211: Connect (ifindex=4)
wpa_supplicant[482]:   * akm=0xfac06
wpa_supplicant[482]:   * Auth Type 0
wpa_supplicant[482]: nl80211: Connect request send successfully
wpa_supplicant[482]: nl80211: Connect event (status=16 ignore_next_local_disconnect=0)
wpa_supplicant[482]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
```

So this NM-level attempt did not exercise a non-SHA256 join.

### Console forced to plain WPA2-PSK

NetworkManager was set to unmanaged for wlan0 at runtime, and a separate wpa_supplicant ran with a temporary configuration under `/run`:

```text
ctrl_interface=/run/e87diag/ctrl
network={
  ssid="e87canbus-jv4xu4p3ip2r"
  key_mgmt=WPA-PSK
  ieee80211w=0
  proto=RSN
  pairwise=CCMP
  group=CCMP
  psk=<redacted>
}
```

```text
1789457299.970592: wlan0: WPA: using KEY_MGMT WPA-PSK
1789457299.970805: wlan0: Trying to associate with SSID 'e87canbus-jv4xu4p3ip2r'
1789457299.973454: nl80211: Connect (ifindex=4)
1789457299.973467:   * bssid_hint=88:a2:9e:ff:6d:38
1789457299.973563:   * akm=0xfac02
1789457299.978854: nl80211: Connect request send successfully
1789457300.342946: nl80211: Connect event (status=16 ignore_next_local_disconnect=0)
1789457300.342996: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
```

## Step 3: result and firmware status

Step 3 failed. The console never reached `wpa_state=COMPLETED`:

```text
$ sudo wpa_cli -i wlan0 status
wpa_state=DISCONNECTED
```

Step 4 (`pmf=2`) was skipped, as the procedure requires when step 3 fails.

### brcmfmac dmesg tail with default debug

The dmesg tail immediately after the first NM attempt, before debug was enabled, contains no failure information:

```text
[    4.733422] brcmfmac: F1 signature read @0x18000000=0x15264345
[    4.751446] brcmfmac: brcmf_fw_alloc_request: using brcm/brcmfmac43455-sdio for chip BCM4345/6
[    4.752725] usbcore: registered new interface driver brcmfmac
[    4.753474] brcmfmac mmc1:0001:1: Direct firmware load for brcm/brcmfmac43455-sdio.raspberrypi,4-model-b.bin failed with error -2
[    5.184879] brcmfmac: brcmf_c_process_txcap_blob: no txcap_blob available (err=-2)
[    5.185291] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM4345/6 wl0: Apr 15 2021 03:03:20 version 7.45.234 (4ca95bb CY) FWID 01-996384e2
[    7.637145] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[    8.169603] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[   11.854355] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[   37.545732] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[  448.493886] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[  486.037184] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[  488.723953] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[  489.268819] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
[  515.538858] brcmfmac: brcmf_dump_obss: dump_obss error (-52)
[  515.540001] brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
```

The September 2026 status-logging patch is not in this kernel.

### brcmfmac with driver debug

The kernel has `CONFIG_BRCMDBG=y` (and `# CONFIG_BRCM_TRACING is not set`), so the writable `debug` module parameter enables real driver logging at runtime. It was set to `0x109406` (TRACE, INFO, EVENT, FIL, CONN, FWCON) for the forced plain-PSK attempt and set back to `0` afterwards. Hexdump and SDIO lines are omitted below:

```text
[  646.608450] brcmfmac: brcmf_cfg80211_connect Enter
[  646.608468] brcmfmac: brcmf_fil_iovar_data_set ifidx=0, name=wpaie, len=22
[  646.608871] brcmfmac: brcmf_vif_set_mgmt_ie bsscfgidx 0, pktflag : 0x20
[  646.608882] brcmfmac: brcmf_cfg80211_connect Applied Vndr IEs for Assoc request
[  646.608887] brcmfmac: brcmf_cfg80211_connect channel=1, center_req=2412, chanspec=0x1001
[  646.608894] brcmfmac: brcmf_cfg80211_connect ie (00000000330da4d4), ie_len (50)
[  646.608901] brcmfmac: brcmf_set_wpa_version setting wpa_auth to 0xc0
[  646.608906] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=wpa_auth, len=4
[  646.609185] brcmfmac: brcmf_set_auth_type open system
[  646.609191] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=auth, len=4
[  646.609477] brcmfmac: brcmf_set_wsec_mode pval (4) gval (4)
[  646.609485] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=wsec, len=4
[  646.610131] brcmfmac: brcmf_fil_bsscfg_data_get ifidx=0, bsscfgidx=0, name=wpa_auth, len=4, err=0
[  646.610152] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=mfp, len=4
[  646.610489] brcmfmac: brcmf_set_key_mgmt setting wpa_auth to 0x80
[  646.610496] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=wpa_auth, len=4
[  646.610805] brcmfmac: brcmf_set_sharedkey key len (0)
[  646.610814] brcmfmac: brcmf_cfg80211_connect using PSK offload
[  646.610819] brcmfmac: brcmf_fil_iovar_data_set ifidx=0, name=sup_wpa, len=4
[  646.611170] brcmfmac: brcmf_fil_cmd_data_set ifidx=0, cmd=268, len=132
[  646.611483] brcmfmac: brcmf_cfg80211_connect SSID "e87canbus-jv4xu4p3ip2r", len (22)
[  646.611492] brcmfmac: brcmf_fil_cmd_int_set ifidx=0, cmd=205, value=0
[  646.611753] brcmfmac: brcmf_fil_iovar_data_set ifidx=0, name=join_pref, len=8
[  646.612140] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=join, len=70
[  646.612999] brcmfmac: brcmf_cfg80211_connect Exit
[  647.012222] brcmfmac: brcmf_rx_event Enter: mmc1:0001:1: rxp=0000000051deb9a2
[  647.012289] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr ff:00:00:00:00:00
[  647.012318] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
[  647.012329] brcmutil: event payload, len=22
[  647.012419] brcmfmac: brcmf_is_nonetwork Processing connecting & no network found
[  647.012440] brcmfmac: brcmf_bss_connect_done Enter
[  647.012477] brcmfmac: brcmf_bss_connect_done Report connect result - connection failed
[  647.012505] brcmfmac: brcmf_bss_connect_done Exit
```

`brcmf_set_key_mgmt` writes `wpa_auth=0x80` (WPA2-PSK), not the SHA256 value. No authentication, association or link event arrives between the `join` iovar and `SET_SSID`. `status 1` is `BRCMF_E_STATUS_FAIL`, not `NO_NETWORKS` (3) or `TIMEOUT` (2). `brcmf_is_nonetwork` treats any non-success `SET_SSID` status as a failed connect, and brcmfmac reports that to cfg80211 as `WLAN_STATUS_AUTH_TIMEOUT` (16).

The firmware console (FWCON) printed only `wl_open` polling lines and one `wlc_phy_set_regtbl_on_femctrl: FIXME bt_coex` line during the window. Nothing mentioned the join.

The `SET_SSID` event's `addr` field changes on every failure and is usually garbage (`ff:00:00:00:00:00`, `00:2c:01:c8:00:14`, `00:00:00:4a:0e:14`, `dd:18:00:50:f2:02`, `dd:09:00:10:18:02`). These byte runs match fragments of the AP's beacon IEs (OBSS scan parameters `4a0e14…2c01c8001400`, WME `dd18 0050f202`, Broadcom `dd09 001018 02`) and, in the cloned-BSSID case, part of the BSSID itself. On successful joins the field holds the real BSSID. This suggests the firmware's failed join fills the event from a scan or BSS buffer at the wrong offset. It is a firmware-internal observation, not a proven cause.

### Firmware PSK offload disabled

`brcmfmac_cyw` and `brcmfmac` were unloaded, and `brcmfmac` was reloaded with `feature_disable=0x282000 debug=0x9404`. Load-time output confirms the mask was received:

```text
[  845.974600] brcmfmac: brcmf_feat_attach Features: 0x342896, disable: 0x282000
```

The forced plain-PSK attempt was then repeated. The connect path no longer contains `using PSK offload`, `sup_wpa` or `cmd=268`, which proves FWSUP was disabled. The failure is unchanged:

```text
[  858.591867] brcmfmac: brcmf_set_key_mgmt setting wpa_auth to 0x80
[  858.591881] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=wpa_auth, len=4
[  858.592271] brcmfmac: brcmf_set_sharedkey key len (0)
[  858.592286] brcmfmac: brcmf_cfg80211_connect SSID "e87canbus-jv4xu4p3ip2r", len (22)
[  858.592704] brcmfmac: brcmf_fil_iovar_data_set ifidx=0, name=join_pref, len=8
[  858.593074] brcmfmac: brcmf_fil_bsscfg_data_set ifidx=0, bsscfgidx=0, name=join, len=70
[  858.984063] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:54:00:08:00:00
[  858.984102] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
[  858.984151] brcmfmac: brcmf_is_nonetwork Processing connecting & no network found
[  858.984175] brcmfmac: brcmf_bss_connect_done Report connect result - connection failed
```

```text
1789457523.379105: wlan0: WPA: using KEY_MGMT WPA-PSK
1789457523.382095:   * akm=0xfac02
1789457523.777745: nl80211: Connect event (status=16 ignore_next_local_disconnect=0)
1789457523.777801: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
```

The driver was then reloaded with no parameters, and NetworkManager management of wlan0 was restored.

## Extended experiments

These were not part of the handoff. They ran with both devices reachable at once, using in-memory NetworkManager profiles (`nmcli connection add save no`) so that no keyfile was touched. The console ran with driver debug `0x8400` (EVENT, CONN) and dmesg streamed to a file. Before each scan, the console's wpa_supplicant BSS table was flushed.

### Open AP, no security

Coordinator: `e87diag-open`, `mode=ap`, `band=bg`, `channel=1`, no `wifi-security`.

```text
$ sudo wpa_cli -i wlan0 status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-open
id=0
mode=AP
wpa_state=COMPLETED
ip_address=10.43.0.1
```

Console:

```text
wpa_supplicant[482]: wlan0: Trying to associate with SSID 'e87diag-open'
wpa_supplicant[482]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
[ 1511.804674] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:2c:01:c8:00:14
[ 1511.804710] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
[ 1511.804746] brcmfmac: brcmf_is_nonetwork Processing connecting & no network found
[ 1511.804767] brcmfmac: brcmf_bss_connect_done Report connect result - connection failed
```

The failure is identical with no RSN at all. Security configuration (AKM, PMF, PSK, ciphers) is fully ruled out for channel 1.

### Roles swapped

Console: open AP `e87diag-swap` on channel 1. Coordinator: station.

```text
wpa_supplicant[454]: wlan0: Trying to associate with SSID 'e87diag-swap'
wpa_supplicant[454]: wlan0: Associated with d8:3a:dd:3c:54:f6
wpa_supplicant[454]: wlan0: CTRL-EVENT-CONNECTED - Connection to d8:3a:dd:3c:54:f6 completed [id=0 id_str=]
wpa_supplicant[454]: wlan0: CTRL-EVENT-REGDOM-CHANGE init=COUNTRY_IE type=COUNTRY alpha2=US
[  406.013011] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr d8:3a:dd:3c:54:f6
[  406.013026] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
[  406.013056] brcmfmac: brcmf_is_linkup Processing set ssid
[  406.015928] brcmfmac: brcmf_bss_connect_done Report connect result - connection succeeded
```

```text
$ sudo ping -c3 -W2 10.44.0.1
64 bytes from 10.44.0.1: icmp_seq=1 ttl=64 time=4014 ms
64 bytes from 10.44.0.1: icmp_seq=2 ttl=64 time=2996 ms
3 packets transmitted, 2 received, 33.3333% packet loss, time 2043ms
```

The coordinator joined the console's AP in about 225 ms. The data path worked, but with 3 to 4 s latency. Seen from the coordinator, the console's AP beacon has the same IE set as the coordinator's AP (country `US`, HT capabilities and operation, OBSS, extended capabilities, WPS, Broadcom and WME vendor IEs), minus RSN:

```text
ie=000c653837646961672d73776170010882848b962430486c0301010504010200000706555320010b1e200100230212002a010032040c1218602d1a210017ff000000000000000000000000000000000000000000003d16010811000000000000000000000000000000000000004a0e14000a002c01c8001400050019007f080500080000000040dd290050f204104a00011010440001021049000600372a0001201011000120105400080000000000000000dd090010180200001c0000dd180050f2020101800003a4000027a4000042435e0062322f00
flags=[WPS][ESS]
```

### Channel, band and BSSID matrix

Coordinator open AP, console station, coordinator at the router:

| Case | Freq | Console level | Console result | Firmware `SET_SSID` | Coordinator `AP-STA-CONNECTED` | Ping |
|---|---|---|---|---|---|---|
| ch1 | 2412 | -61 | 3 rejects | status 1 | none | 0/3 |
| ch1 repeat | 2412 | -55 | 2 rejects | status 1 | none | 0/3 |
| ch1, cloned BSSID `02:e8:7d:1a:90:01` | 2412 | -63 | 2 rejects | status 1 | none | 0/3 |
| ch6 | 2437 | -58 | 2 rejects, then connected | status 1, then success | yes, including during the "rejected" first attempt | 0/2, ARP `FAILED` |
| ch6 repeat | 2437 | not listed | 2 rejects | status 3, then status 1 | none | 0/3 |
| **ch11** | 2462 | -61 | **connected, first attempt** | **status 0** | yes | **3/3** |
| **ch11 repeat 1** | 2462 | not recorded | **connected, first attempt** | **status 0** | yes | **3/3** |
| **ch11 repeat 2** | 2462 | not recorded | **connected, first attempt** | **status 0** | yes | **3/3** |
| ch36 (5 GHz) | 5180 | -62 | 3 rejects, about 100 ms each | status 1 | none | 0/3 |
| ch149 (5 GHz) | 5745 | not listed | 2 rejects | status 1 | yes, 250 ms before the console's reject | 0/3 |

The first channel 6 repeat (not in the table) was invalid: the console still held the stale channel 11 scan entry and got `status 3`. It was rerun with the BSS table flushed.

Channel 11 success:

```text
Sep 15 07:47:34.225817 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 07:47:34.408052 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 07:47:34.408760 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
[ 1789.630880] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
[ 1789.630917] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
wpa_state=COMPLETED
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
Sep 15 07:47:34.356632 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
```

Channel 6, where the AP accepted a join that the console firmware reported as failed:

```text
Sep 15 07:45:11.909479 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 07:45:12.178551 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
Sep 15 07:45:15.476553 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 07:45:19.625493 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 07:45:19.652853 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Associated with 88:a2:9e:ff:6d:38
```

The resulting link had no working data path. The coordinator's station entry showed empty association fields:

```text
d8:3a:dd:3c:54:f6
flags=[AUTH][ASSOC][AUTHORIZED][MAYBE_WPS]
aid=0
capability=0x0
listen_interval=0
supported_rates=02 04 0b 16
timeout_next=NULLFUNC POLL
rx_packets=15
tx_packets=32
```

```text
$ sudo ping -c5 -W3 10.43.0.1
5 packets transmitted, 0 received, +5 errors, 100% packet loss, time 4095ms
$ ip neigh show dev wlan0
10.43.0.1 FAILED 
```

The station entry on the successful channel 11 joins shows the same `aid=0` and `supported_rates=02 04 0b 16`, so those fields are likely NM or firmware AP-mode reporting artefacts rather than a cause.

Channel 149:

```text
Sep 15 07:54:02.449926 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 07:54:02.565284 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 07:54:02.812942 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
[ 2178.059991] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr c3:5d:80:1e:88:6c
[ 2178.060033] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 07:54:15.905496 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
```

With a cloned BSSID on channel 1, the driver scanned and connected to the cloned address. wpa_supplicant's `bssid=88:a2:9e:ff:6d:38` in the reject line is a stale label:

```text
[ 2242.049839] brcmfmac: brcmf_inform_single_bss bssid: 02:e8:7d:1a:90:01
[ 2247.851071] brcmfmac: brcmf_cfg80211_connect channel=1, center_req=2412, chanspec=0x1001
[ 2247.852116] brcmfmac: brcmf_cfg80211_connect SSID "e87diag-open", len (12)
[ 2248.209963] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr dd:09:00:10:18:02
[ 2248.210006] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
[ 2261.622355] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 7d:1a:90:01:77:6c
[ 2261.622396] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
```

### Coordinator driver events during a channel 1 failure

Coordinator open AP on channel 1 with driver debug `0x8400`. The console made two failed attempts (`SET_SSID status 1` at 07:56:53 and 07:57:07). Between the markers the coordinator's firmware raised no events at all, not even ones excluded from the filter below:

```text
      1 [ 1213.928973] E87DIAG coordAP-end 2026-09-15T07:57:22+00:00
      1 [ 1172.163083] E87DIAG coordAP-start 2026-09-15T07:56:40+00:00
```

This confirms that in this failure mode nothing from the console reaches the AP as an authentication or association. brcmfmac does not register for probe-request events here, so probe requests cannot be ruled in or out.

## Restore

Temporary NetworkManager profiles were deleted on both devices. Each keyfile was restored with `cp -a` from its step 0 backup.

Coordinator:

```text
$ sudo sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection /root/e87canbus-wifi.nmconnection.bak
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /root/e87canbus-wifi.nmconnection.bak
-rw------- 1 root root  355 Sep 14 18:55 e87canbus-wifi.nmconnection
$ sudo nmcli connection reload
$ sudo nmcli connection up e87canbus-coordinator-wifi
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/20)
$ sudo wpa_cli -i wlan0 status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
id=0
mode=AP
wifi_generation=4
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.1
$ sudo cat /sys/module/brcmfmac/parameters/debug
0
```

Console:

```text
$ sudo sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection /root/e87canbus-wifi.nmconnection.bak
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /root/e87canbus-wifi.nmconnection.bak
-rw------- 1 root root  363 Sep 14 19:03 e87canbus-wifi.nmconnection
$ sudo nmcli connection reload
pmf=3
$ sudo wpa_cli -i wlan0 status | grep wpa_state
wpa_state=SCANNING
wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
$ sudo cat /sys/module/brcmfmac/parameters/debug
0
$ lsmod | grep -E "^brcm"
brcmfmac_cyw           12288  0
brcmfmac              376832  1 brcmfmac_cyw
brcmutil               24576  1 brcmfmac
```

After restore the console is back to its original failing state. Both backups, the scheduled-job script and log, and every temporary script and log were then removed from both devices, and `e87-pmf-flip.service` no longer exists.

The following changed at runtime and has been reverted: both Wi-Fi keyfiles (restored byte-exactly), the console brcmfmac module (reloaded twice, now loaded with default parameters), the `debug` parameter on both devices (back to `0`), NetworkManager management of the console's wlan0 (managed again), and in-memory NetworkManager profiles (deleted). Some runtime state did not survive: the coordinator's uptime reset when it was moved to the router, and the `system-connections` directory mtimes changed on both devices.

The cards were modified at runtime and then restored, but they remain diagnostic. Final gate evidence must come from freshly provisioned clean cards.

## Follow-up: production profile, neighbouring AP, regulatory domain and display

These experiments ran later the same morning, with both devices reachable at once. As before, they used in-memory NetworkManager profiles, this time created by copying each device's generated keyfile into `/run/NetworkManager/system-connections` with only `id`, `ssid` (`e87diag-prod`), `autoconnect` and the AP `band`/`channel` changed. Security was exactly as generated (`key-mgmt=wpa-psk`, `proto=rsn`, `pairwise=ccmp`, `group=ccmp`, `pmf=3`, provisioned PSK). The console used driver debug `0x8400`, and before each scan its wpa_supplicant BSS table was flushed.

The coordinator's test AP:

```text
[wifi]
mode=ap
ssid=e87diag-prod
band=bg
channel=11

[wifi-security]
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
psk=<redacted>
```

### Production security profile by channel

Home 2.4 GHz AP on channel 2, console DSI display attached:

| Run | Coordinator channel | Console result | Coordinator | Ping |
|---|---|---|---|---|
| 1 | 11 | connected, `key_mgmt=WPA2-PSK-SHA256`, `pmf=2` | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 13 to 21 ms |
| 2 | 11 | connected | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 9 to 12 ms |
| 3 | 11 | connected | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 11 to 12 ms |
| control | 1 | 5 × `ASSOC-REJECT status_code=16`, firmware `SET_SSID status 1` | nothing | 0/3 |

```text
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2462
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=15.2 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=13.4 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=21.0 ms
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
=== supplicant
Sep 15 08:06:37.576924 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 08:06:37.684617 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 08:06:37.684726 e87-console-ef27d0966bdd wpa_supplicant[482]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
=== firmware SET_SSID
[ 2932.905064] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
[ 2932.905099] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
--- coordinator
Sep 15 08:06:37.704898 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 08:06:37.705791 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
```

### Home AP moved to channel 11

This test checked whether the failure follows the neighbouring network. The home 2.4 GHz AP was moved from channel 2 to channel 11:

```text
d0:21:f9:bf:a2:cd	2462	-43	[WPA2-PSK+SAE-CCMP][ESS]	Aileoze_2.4
30:68:93:22:96:72	2457	-73	[WPA2-PSK+FT/PSK-CCMP][WPS][ESS]	SHELL D90CB7
```

| Coordinator channel | Runs | Result |
|---|---|---|
| 1 (now clear) | 4 (12 attempts) | all `ASSOC-REJECT status_code=16`, firmware `SET_SSID status 1`, nothing at the coordinator |
| 11 (shared with home AP at -46 dBm) | 3 | all connected first attempt, `EAPOL-4WAY-HS-COMPLETED`, ping 3/3 |

The failure did not follow the neighbouring network. In the display-attached state, the console's scans caught the coordinator's channel 1 AP only intermittently (about 1 scan in 3, and one run needed 5 scans), while the channel 11 AP was found on the first scan every time. Without the display (below), the same channel 1 AP appeared in 9 scans out of 10.

### Regulatory domain

Country GB was set at runtime on both devices with `wpa_cli -i wlan0 set country GB`. brcmfmac passed it to the firmware:

```text
wpa_supplicant[454]: wlan0: CTRL-EVENT-REGDOM-CHANGE init=USER type=COUNTRY alpha2=GB
[ 2923.338303] brcmfmac: brcmf_cfg80211_reg_notifier Enter: initiator=1, alpha=GB
[ 2923.338313] brcmfmac: brcmf_translate_country_code No country codes configured for device, using ISO3166 code and 0 rev
```

The coordinator's beacon country IE changed to `0706474220010d14` (GB, channels 1 to 13). Channel 1 still failed: 2 runs, 7 attempts, firmware `SET_SSID status 1` (one `status 3`), with nothing at the coordinator. The country was then set back to `00` on both devices:

```text
wpa_supplicant[454]: wlan0: CTRL-EVENT-REGDOM-CHANGE init=USER type=WORLD
wpa_supplicant[457]: wlan0: CTRL-EVENT-REGDOM-CHANGE init=USER type=WORLD
```

### Hardware difference between the devices

```text
coordinator: dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
coordinator: dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000
coordinator: dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000
coordinator: card1-HDMI-A-1 disconnected, card1-HDMI-A-2 disconnected (no display)

console: dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000
console: card1-DSI-1 status=connected enabled=enabled mode=800x480
console: card1-HDMI-A-1 status=disconnected enabled=disabled
```

The coordinator carries more MCP2515 CAN hardware than the console, so the CAN boards are not the console-specific factor. The DSI touchscreen is.

### Console DSI display disconnected

The console was powered down, its DSI ribbon disconnected, and it was booted again. The home 2.4 GHz AP was back on channel 1, and the coordinator's production-security test AP was on channel 1.

```text
card1-HDMI-A-1 status=disconnected enabled=disabled
card1-HDMI-A-2 status=disconnected enabled=disabled
card1-Writeback-1 status=unknown enabled=disabled
```

Ten flushed scans:

```text
scan 1: Aileoze_2.4@2412/-51  e87diag-prod@2412/-63  
scan 2: Aileoze_2.4@2412/-51  e87diag-prod@2412/-64  SKY5QDNP@2462/-73  SKYJCRY2@2462/-78  
scan 3: Aileoze_2.4@2412/-50  @2457/-74  SKY5QDNP@2462/-75  SHELL D90CB7_Guest@2457/-75  SKYJCRY2@2462/-76  Vodafone4E6670@2447/-77  
scan 4: Aileoze_2.4@2412/-51  Vodafone4E6670@2447/-77  e87diag-prod@2412/-62  SHELL D90CB7@2457/-72  @2457/-72  SHELL D90CB7_Guest@2457/-72  SKY5QDNP@2462/-76  SKYJCRY2@2462/-78  
scan 5: Aileoze_2.4@2412/-51  e87diag-prod@2412/-64  SKYJCRY2@2462/-72  SHELL D90CB7@2457/-74  SHELL D90CB7_Guest@2457/-75  Vodafone4E6670@2447/-78  
scan 6: Aileoze_2.4@2412/-53  e87diag-prod@2412/-63  SHELL D90CB7@2457/-73  SKYJCRY2@2462/-74  Vodafone4E6670@2447/-76  BT-FSF66R@2437/-77  \x00\x00\x00\x00\x00\x00\x00\x00\x00@2437/-77  SKY5QDNP@2462/-81  EE WiFi@2437/-71  
scan 7: Aileoze_2.4@2412/-49  e87diag-prod@2412/-62  Vodafone4E6670@2447/-76  SKYJCRY2@2462/-76  BT-FSF66R@2437/-76  EE WiFi@2437/-71  
scan 8: Aileoze_2.4@2412/-53  e87diag-prod@2412/-65  \x00\x00\x00\x00\x00\x00\x00\x00\x00@2437/-69  Vodafone4E6670@2447/-74  SHELL D90CB7@2457/-75  SHELL D90CB7_Guest@2457/-75  @2457/-76  BT-FSF66R@2437/-77  EE WiFi@2437/-71  
scan 9: Aileoze_2.4@2412/-46  e87diag-prod@2412/-51  BT-FSF66R@2437/-69  SHELL D90CB7@2457/-73  SKYJCRY2@2462/-74  SKY5QDNP@2462/-77  EE WiFi@2437/-74  
scan 10: Aileoze_2.4@2412/-45  e87diag-prod@2412/-51  Vodafone4E6670@2447/-69  SKYJCRY2@2462/-70  BT-FSF66R@2437/-71  SKY5QDNP@2462/-73  SHELL D90CB7_Guest@2457/-75  SKYJCRY2@2462/-76  EE WiFi@2437/-72  
coordinator AP seen 9/10, Aileoze_2.4 seen 10/10
```

Without the display, the console receives neighbouring networks at -69 to -81 dBm across channels 6 to 11. None of those appeared in any display-attached scan during the session, which only ever showed the home AP and the coordinator.

Production security profile on channel 1, three runs:

| Run | Console result | Coordinator | Ping |
|---|---|---|---|
| 1 | connected first attempt, `key_mgmt=WPA2-PSK-SHA256` | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 7 to 23 ms |
| 2 | connected first attempt | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 6 to 12 ms |
| 3 | connected first attempt | `AP-STA-CONNECTED`, `EAPOL-4WAY-HS-COMPLETED` | 3/3, 7 to 14 ms |

```text
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.2
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=23.3 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=7.46 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=14.3 ms
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
Sep 15 08:53:29.758392 e87-console-ef27d0966bdd wpa_supplicant[457]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 08:53:29.962041 e87-console-ef27d0966bdd wpa_supplicant[457]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 08:53:29.962113 e87-console-ef27d0966bdd wpa_supplicant[457]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
Sep 15 08:53:29.898763 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 08:53:29.899473 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
```

### Follow-up restore

Both in-memory profiles were deleted, and the coordinator's real AP was reactivated. Temporary scripts and logs were removed.

```text
console:     5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
coordinator: 0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
coordinator: freq=2412 ssid=e87canbus-jv4xu4p3ip2r key_mgmt=WPA2-PSK-SHA256 wpa_state=COMPLETED
both:        /sys/module/brcmfmac/parameters/debug = 0
```

With the display still disconnected, the console's unmodified provisioned profile then connected to the coordinator's unmodified AP by itself:

```text
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.2
NAME                    DEVICE  STATE     
Wired connection 1      end0    activated 
e87canbus-console-wifi  wlan0   activated 
lo                      lo      activated 
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=15.3 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=11.6 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=9.95 ms
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
```

The console DSI display was left disconnected at the end of the session.

## Conclusion and next decision

**Cause:** the console's DSI touchscreen desensitises its 2.4 GHz receiver. With the display attached, the console barely hears the band, and its firmware's join fails locally (`SET_SSID status 1`, reported as status 16) on channel 1 and elsewhere. With the display disconnected, the unmodified provisioned pair connects on channel 1 with the required PMF and SHA256 AKM. Channel 11's success with the display attached shows that the interference is uneven across the band, not that channel 11 is a fix.

**Ruled out:** the SHA256 AKM, PMF, RSN security in general, firmware PSK offload (`feature_disable=0x282000` confirmed applied), neighbouring-AP overlap, regulatory domain or country IE, BSSID, and signal level.

**Implications:**

- The Debian firmware change (`2827f7e`) and the Raspberry Pi Bookworm 6.12 kernel isolation (`908f835`) were both aimed at a software cause that this evidence does not support. Neither is needed to explain or fix status 16. The original Raspberry Pi firmware package has not been tested with the display disconnected, so reverting to it needs its own gate run.
- `pmf=3` in `_network_profile` (`e87ctl/src/e87ctl/provisioning.py`) and ADR 0014 are unaffected. Pinning a channel is not a justified fix.
- The fix is physical or electrical: display ribbon routing, shielding or ferrites, antenna separation, or a different display interface or panel. It needs to be designed and validated with the console hardware as it will be installed in the car, since the coupling depends on cable and enclosure layout.
- A gate that runs with the display attached will keep failing until that is addressed. A gate that runs with it disconnected proves the software but not the installed hardware.

How to address the display interference, whether to keep or revert `2827f7e` and `908f835`, and how to restructure the physical gate are Aidan's decisions and are not made here.
