# Candidate 2827f7e DSI interference verification

Date: 2026-09-15  
Follow-on to: [`2827f7e-pmf-akm-test.md`](2827f7e-pmf-akm-test.md)  
Devices: coordinator `e87-coordinator-1069df5e6c91`, console `e87-console-ef27d0966bdd` (same diagnostic cards, candidate `2827f7e`, profile `bench`)

## Result

**Test A confirms the interference finding.** The 2.4 GHz scan census followed the DSI ribbon across three boots. The ribbon was disconnected, attached, then disconnected again, and the result was not explained by rebooting:

| Phase | Boot ID | DSI connector | 2.4 GHz networks per scan | Distinct 2.4 GHz networks | Weakest 2.4 GHz level | Coordinator AP in census | Home 2.4 GHz AP in census | 5 GHz networks per scan |
|---|---|---|---|---|---|---|---|---|
| 1 | `6b27065f…` | absent | 4 to 9 (mean 6.3) | 10 | -81 dBm | 10/10 | 10/10 | 3 |
| 2 | `ba7121cc…` | `connected enabled` 800x480 | **0 to 2 (mean 1.0)** | **3** | -75 dBm | **0/10** | 5/10 | 3 |
| 3 | `b2886ac3…` | absent | 3 to 9 (mean 6.6) | 10 | -85 dBm | 5/10 | 10/10 | 3 |

Channel 1 joins with the production security profile tracked the ribbon too:

| Phase | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| 1 (ribbon off) | `SET_SSID status 0`, 4-way done, ping 3/3 | `status 0`, 4-way done, ping 3/3 | `status 0`, 4-way done, ping 3/3 |
| 2 (ribbon on) | AP not found in 6 scans, no attempt | AP not found in 6 scans, no attempt | AP found on 2nd scan, 4 attempts, `status 3` then `status 1` ×3, coordinator silent |
| 3 (ribbon off) | `status 0`, 4-way done, ping 3/3 | `status 0`, 4-way done, NM activated, ping 0/3 | NM pre-connect scan did not find the AP, no attempt |

5 GHz reception was unaffected by the ribbon in every census: the same three channel 36 networks at similar levels in all 30 scans.

**Test B is a split result.** With the ribbon disconnected, an open AP on channel 36 failed 3 of 3 runs (8 attempts, all `SET_SSID status 1`, no `AP-STA-CONNECTED`). Channel 149 connected in 2 of 3 runs. Run 1 connected on the first attempt with ping 2/3. Run 2 connected on the third attempt with ping 2/3. Run 3 failed 5 attempts, while the coordinator logged `AP-STA-CONNECTED` twice. As the addendum requires for a split result, this is reported without a theory.

## Method and constraints

- **Runtime-only.** No repo edits other than this file, no commits, no changes to `2827f7e`, `908f835` or `_network_profile`.
- **Coordinator APs:** the production AP was an in-memory copy of the generated keyfile in `/run/NetworkManager/system-connections`, changing only `id`, `ssid=e87diag-prod`, `autoconnect=false`, `band=bg` and `channel`. Security was exactly as generated (`pmf=3`, provisioned PSK, printed redacted). The Test B open AP was `nmcli connection add save no`, `ssid=e87diag-open`.
- **Console stations:** equivalent in-memory copies. For each run the console flushed its wpa_supplicant BSS table, rescanned up to 6 times until the target SSID appeared, then ran `nmcli connection up` with a 30 s wait and `ping -c3`. Driver debug was `0x8400` for the run only.
- **Firmware events:** `SET_SSID` lines come from `journalctl -k`, bracketed by `/dev/kmsg` markers. The first phase 1 run used `dmesg -w` into a file, which did not capture the lines, so its script printed nothing under `--- firmware SET_SSID` and failed to remove its temp files. The same window was recovered from `journalctl -k` immediately afterwards (below), and the script was switched to `journalctl -k` for every later run.
- **Scan census:** 10 scans, each preceded by `wpa_cli bss_flush 0`, with 7 s to complete. Each scan lists every BSS as frequency, level, BSSID and SSID.
- **The DSI ribbon was changed only with the console powered off.** The console was powered off with `systemd-run --on-active=2 systemctl poweroff`. Aidan then changed the ribbon and restored power.
- **Clock:** the console has no RTC. At the start of phase 2 its clock was about 2.5 minutes behind the Mac (console `09:30:22`, Mac `09:32:51`) until NTP synchronised during that phase. State transitions below use the Mac's UTC. The phase 2 boot's `booted=` and `journalctl --list-boots` values are from before the clock synced.
- **No `/root` keyfile backups existed**, because the previous session had removed them after a verified restore. None were needed, since no keyfile was modified. Keyfile hashes were verified against the recorded values at the start, at each boot and at the end.
- **The PSK is absent** from every captured log (checked by exact-string search).

## State transitions (Mac UTC)

| Time | Event |
|---|---|
| before 09:18:43 | Aidan rebooted the console. Ribbon disconnected (state carried from the previous session). |
| 09:19:56 | Console reachable. Boot `6b27065f-e826-4bd5-b054-e3a4c68820f9`, `card1-DSI-1` absent. **Phase 1.** |
| 09:20:41 | Coordinator `e87diag-prod` AP up on channel 1 |
| 09:20:49 to 09:21:43 | Phase 1 channel 1 runs |
| 09:22:39 to 09:23:50 | Phase 1 census |
| 09:24:02 to 09:29:06 | Test B, channels 36 and 149 (same boot, ribbon off) |
| 09:29:21 | Coordinator `e87diag-prod` AP back on channel 1 |
| 09:29:26 | **Transition 1:** console poweroff requested. Unreachable by 09:29:56. |
| about 09:33 | Aidan reports power-on with the ribbon reattached |
| 09:32:51 | Console reachable. Boot `ba7121cc-1b9f-494d-9ee7-ce32b0380868`, `card1-DSI-1 status=connected enabled=enabled mode=800x480`, kiosk service active. **Phase 2.** |
| 09:33:07 to 09:36:17 | Phase 2 channel 1 runs |
| 09:36:25 to 09:37:38 | Phase 2 census |
| 09:37:52 | **Transition 2:** console poweroff requested. Unreachable by 09:38:15. |
| about 09:39 | Aidan reports power-on with the ribbon disconnected |
| 09:40:14 | Console reachable. Boot `b2886ac3-52d1-461b-a093-9f8d45e2f732`, `card1-DSI-1` absent, `NTPSynchronized=yes`. **Phase 3.** |
| 09:40:25 to 09:41:44 | Phase 3 channel 1 runs |
| 09:41:45 to 09:42:57 | Phase 3 census |
| 09:43:24 | Restore |
| 09:43:54 | Console's provisioned profile auto-connected to the coordinator's provisioned AP |

## Phase 0: baseline

The coordinator was captured at 09:18:45. The console was captured at 09:19:56, after its Ethernet link came back.

```text
=== PHASE 0 baseline, local time 2026-09-15T09:18:45Z
--- c
2026-09-15T09:18:46+00:00
e87-coordinator-1069df5e6c91
boot_id=58dae398-7d42-4422-9b5d-1c7de37b8b33
booted=2026-09-15 07:37:08
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
debug=0
card1-HDMI-A-1 status=disconnected enabled=disabled
card1-HDMI-A-2 status=disconnected enabled=disabled
card1-Writeback-1 status=unknown enabled=disabled
NAME                        DEVICE  STATE     
Wired connection 1          end0    activated 
e87canbus-coordinator-wifi  wlan0   activated 
lo                          lo      activated 
Wired connection 1.nmconnection
lo.nmconnection
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.1
--- k
(eval):5: no such file or directory: /tmp/e87key2/k
=== PHASE 0 console baseline, local 2026-09-15T09:19:56Z
2026-09-15T09:19:57+00:00
e87-console-ef27d0966bdd
boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
booted=2026-09-15 09:18:43
Hint: You are currently not seeing messages from other users and the system.
      Users in groups 'adm', 'systemd-journal' can see all messages.
      Pass -q to turn off this notice.
 -3 5e1debbc37fc4fd6b8bdd09da4f94a89 Mon 2026-09-14 19:49:39 UTC Mon 2026-09-14 20:04:12 UTC
 -2 4ab3a216e22a4192a0af3c278256796d Tue 2026-09-15 07:21:53 UTC Tue 2026-09-15 08:28:47 UTC
 -1 4a7cd3ba4c374f14b0d7e24364e9a178 Tue 2026-09-15 08:51:52 UTC Tue 2026-09-15 08:55:20 UTC
  0 6b27065fe8264bd5b054e3a4c68820f9 Tue 2026-09-15 09:19:57 UTC Tue 2026-09-15 09:19:57 UTC
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
debug=0
card1-HDMI-A-1 status=disconnected enabled=disabled
card1-HDMI-A-2 status=disconnected enabled=disabled
card1-Writeback-1 status=unknown enabled=disabled
NAME                    DEVICE  STATE     
Wired connection 1      end0    activated 
e87canbus-console-wifi  wlan0   activated 
lo                      lo      activated 
Wired connection 1.nmconnection
lo.nmconnection
```

## Phase 1: ribbon disconnected (boot `6b27065f`)

### Channel 1 joins

```text
##### PHASE 1 (ribbon disconnected) Test A step 1: coordinator prod AP ch1, local 2026-09-15T09:20:41Z
$ /run/NetworkManager/system-connections/e87diag-prod-ap.nmconnection (psk redacted)
[connection]
id=e87diag-prod-ap
type=wifi
interface-name=wlan0
autoconnect=false

[wifi]
mode=ap
ssid=e87diag-prod
band=bg
channel=1

[wifi-security]
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
psk=<redacted>

[ipv4]
address1=10.42.0.1/24
method=manual
never-default=true
ignore-auto-dns=true

[ipv6]
method=disabled
2026-09-15T09:20:42+00:00 $ nmcli connection up e87diag-prod-ap
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/26)
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
mode=AP
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.1
$ /run/NetworkManager/system-connections/e87diag-prod-sta.nmconnection (psk redacted)
[connection]
id=e87diag-prod-sta
type=wifi
interface-name=wlan0
autoconnect=false

[wifi]
mode=infrastructure
ssid=e87diag-prod

[wifi-security]
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
psk=<redacted>

[ipv4]
address1=10.42.0.2/24
method=manual
never-default=true
ignore-auto-dns=true

[ipv6]
method=disabled
=== p1-ch1-run1 start 2026-09-15T09:20:49+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-64	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:20:55+00:00 $ nmcli connection up e87diag-prod-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/4)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping -c3 10.42.0.1
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=8.59 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=12.9 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=8.63 ms
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
--- supplicant
Sep 15 09:20:59.206016 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:20:59.315170 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:20:59.315291 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
[  135.959171] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
[  135.959201] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
rm: cannot remove '/tmp/dm-p1-ch1-run1.txt': Operation not permitted
rm: cannot remove '/tmp/dm-p1-ch1-run1.pid': Operation not permitted
=== p1-ch1-run1 end 2026-09-15T09:21:05+00:00
--- coordinator
Sep 15 09:20:59.308196 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:20:59.309241 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
Sep 15 09:21:04.976487 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p1-ch1-run2 start 2026-09-15T09:21:07+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-65	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:21:15+00:00 $ nmcli connection up e87diag-prod-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/5)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping -c3 10.42.0.1
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=15.2 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=20.9 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=9.50 ms
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
--- supplicant
Sep 15 09:21:18.481983 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:21:18.660175 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:21:18.660290 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
[  155.320382] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
[  155.320418] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
rm: cannot remove '/tmp/dm-p1-ch1-run2.txt': Operation not permitted
rm: cannot remove '/tmp/dm-p1-ch1-run2.pid': Operation not permitted
=== p1-ch1-run2 end 2026-09-15T09:21:24+00:00
--- coordinator
Sep 15 09:21:18.588886 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:21:18.589665 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
Sep 15 09:21:24.210901 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p1-ch1-run3 start 2026-09-15T09:21:26+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-65	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:21:34+00:00 $ nmcli connection up e87diag-prod-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/6)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping -c3 10.42.0.1
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=17.5 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=15.5 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=7.53 ms
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
--- supplicant
Sep 15 09:21:37.745980 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:21:37.899507 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:21:37.899629 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
[  174.566679] brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
[  174.566716] brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
rm: cannot remove '/tmp/dm-p1-ch1-run3.txt': Operation not permitted
rm: cannot remove '/tmp/dm-p1-ch1-run3.pid': Operation not permitted
=== p1-ch1-run3 end 2026-09-15T09:21:43+00:00
--- coordinator
Sep 15 09:21:24.210901 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:21:37.846314 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:21:37.847055 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
Sep 15 09:21:43.421068 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
```

`SET_SSID` recovered from `journalctl -k` for the same window:

```text
Sep 15 09:20:49.443497 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run1-start 2026-09-15T09:20:49+00:00
Sep 15 09:20:59.307630 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:20:59.307750 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
Sep 15 09:21:03.599556 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run1-end 2026-09-15T09:21:03+00:00
Sep 15 09:21:07.231462 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run2-start 2026-09-15T09:21:07+00:00
Sep 15 09:21:18.655594 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:21:18.655735 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
Sep 15 09:21:23.023524 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run2-end 2026-09-15T09:21:23+00:00
Sep 15 09:21:26.499471 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run3-start 2026-09-15T09:21:26+00:00
Sep 15 09:21:37.895752 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:21:37.895922 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
Sep 15 09:21:42.227487 e87-console-ef27d0966bdd unknown: E87DIAG p1-ch1-run3-end 2026-09-15T09:21:42+00:00
```

### Census

```text
=== census phase1-ribbon-off start 2026-09-15T09:22:39+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
card1-DSI-1 absent
scan 1 09:22:46: total=8 2.4GHz=5 5GHz=3 weakest=-80
    2412 -65 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -44 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -79 6a:b6:87:89:e8:8a EE WiFi
    2437 -80 ac:b6:87:89:e8:89 BT-FSF66R
    2462 -78 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 2 09:22:53: total=9 2.4GHz=6 5GHz=3 weakest=-79
    2412 -55 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -43 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -79 6a:b6:87:89:e8:8a EE WiFi
    2437 -74 ac:b6:87:89:e8:89 BT-FSF66R
    2457 -74 30:68:93:22:96:72 SHELL D90CB7
    2462 -72 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -71 38:a6:ce:86:b8:d5 SKYEA800
    5180 -48 d0:21:f9:bf:a2:ce Aileoze_5
scan 3 09:23:00: total=8 2.4GHz=5 5GHz=3 weakest=-78
    2412 -66 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -47 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -78 ac:b6:87:89:e8:89 BT-FSF66R
    2447 -75 62:d8:a4:45:2b:96 Vodafone4E6670
    2462 -77 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -51 d0:21:f9:bf:a2:ce Aileoze_5
scan 4 09:23:08: total=10 2.4GHz=7 5GHz=3 weakest=-78
    2412 -59 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -43 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -76 6a:b6:87:89:e8:8a EE WiFi
    2437 -76 ac:b6:87:89:e8:89 BT-FSF66R
    2457 -75 30:68:93:22:96:72 SHELL D90CB7
    2462 -78 3c:9e:c7:9d:e1:f2 SKYJCRY2
    2462 -67 c0:a3:6e:7e:1f:52 SKY5QDNP
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 5 09:23:15: total=10 2.4GHz=7 5GHz=3 weakest=-79
    2412 -54 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -43 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -79 6a:b6:87:89:e8:8a EE WiFi
    2437 -73 ac:b6:87:89:e8:89 BT-FSF66R
    2447 -77 62:d8:a4:45:2b:96 Vodafone4E6670
    2457 -75 30:68:93:22:96:72 SHELL D90CB7
    2462 -78 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -70 38:a6:ce:86:b8:d5 SKYEA800
    5180 -48 d0:21:f9:bf:a2:ce Aileoze_5
scan 6 09:23:22: total=9 2.4GHz=6 5GHz=3 weakest=-78
    2412 -66 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -44 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -74 6a:b6:87:89:e8:8a EE WiFi
    2437 -78 ac:b6:87:89:e8:89 BT-FSF66R
    2447 -77 62:d8:a4:45:2b:96 Vodafone4E6670
    2462 -75 c0:a3:6e:7e:1f:52 SKY5QDNP
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 7 09:23:29: total=7 2.4GHz=4 5GHz=3 weakest=-81
    2412 -55 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -45 d0:21:f9:bf:a2:cd Aileoze_2.4
    2447 -78 62:d8:a4:45:2b:96 Vodafone4E6670
    2462 -81 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -48 d0:21:f9:bf:a2:ce Aileoze_5
scan 8 09:23:36: total=10 2.4GHz=7 5GHz=3 weakest=-77
    2412 -55 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -44 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -77 6a:b6:87:89:e8:8a EE WiFi
    2437 -76 ac:b6:87:89:e8:89 BT-FSF66R
    2457 -77 36:68:93:22:96:72 
    2457 -75 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -71 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -70 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 9 09:23:43: total=12 2.4GHz=9 5GHz=3 weakest=-78
    2412 -54 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -44 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -74 6a:b6:87:89:e8:8a EE WiFi
    2437 -76 ac:b6:87:89:e8:89 BT-FSF66R
    2447 -78 62:d8:a4:45:2b:96 Vodafone4E6670
    2457 -75 30:68:93:22:96:72 SHELL D90CB7
    2457 -73 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -78 3c:9e:c7:9d:e1:f2 SKYJCRY2
    2462 -77 c0:a3:6e:7e:1f:52 SKY5QDNP
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 10 09:23:50: total=10 2.4GHz=7 5GHz=3 weakest=-79
    2412 -66 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -43 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -77 6a:b6:87:89:e8:8a EE WiFi
    2437 -79 ac:b6:87:89:e8:89 BT-FSF66R
    2447 -76 62:d8:a4:45:2b:96 Vodafone4E6670
    2462 -73 3c:9e:c7:9d:e1:f2 SKYJCRY2
    2462 -78 c0:a3:6e:7e:1f:52 SKY5QDNP
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -71 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
=== census phase1-ribbon-off end 2026-09-15T09:23:50+00:00
```

## Test B: 5 GHz, ribbon disconnected (boot `6b27065f`)

### Channel 36

```text
##### TEST B ch36 (ribbon disconnected), local 2026-09-15T09:24:02Z
2026-09-15T09:24:03+00:00 $ nmcli connection up e87diag-open-ap
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/27)
bssid=88:a2:9e:ff:6d:38
freq=5180
ssid=e87diag-open
mode=AP
wpa_state=COMPLETED
ip_address=10.43.0.1
--- console flushed scan (5 GHz)
boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9 2026-09-15T09:24:08+00:00
scan attempts: 4
bssid / frequency / signal level / flags / ssid
d0:21:f9:bf:a2:ce	5180	-49	[WPA2-PSK+SAE-CCMP][ESS]	Aileoze_5
38:a6:ce:86:b8:d5	5180	-69	[WPA2-PSK-CCMP][WPS][ESS]	SKYEA800
20:47:ed:a8:43:23	5180	-70	[WPA2-PSK-CCMP][WPS-AUTH][ESS]	SKY00973
=== b-ch36-run1 start 2026-09-15T09:24:37+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 6
2026-09-15T09:25:13+00:00 $ nmcli connection up e87diag-open-sta
Error: Connection activation failed: 802.1X supplicant took too long to authenticate
Hint: use 'journalctl -xe NM_CONNECTION=ebb00c78-7fda-47be-8546-33ec08904fd7 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=INACTIVE
$ ping -c3 10.43.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2046ms
--- supplicant
Sep 15 09:25:17.806770 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:25:17.955011 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:25:21.306632 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:25:21.438440 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:25:25.199092 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:25:25.428092 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:25:29.690546 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:25:29.843359 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
--- firmware SET_SSID
Sep 15 09:25:17.955651 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 2f:00:1c:00:00:00
Sep 15 09:25:17.955848 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:25:21.439719 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:dd:09:00:10:18
Sep 15 09:25:21.439905 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:25:25.431752 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:40:bf
Sep 15 09:25:25.431854 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:25:29.844046 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:00:00
Sep 15 09:25:29.844283 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
=== b-ch36-run1 end 2026-09-15T09:25:48+00:00
--- coordinator
=== b-ch36-run2 start 2026-09-15T09:25:49+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	5180	-66	[WPS][ESS]	e87diag-open
2026-09-15T09:25:56+00:00 $ nmcli connection up e87diag-open-sta
Error: Connection activation failed: 802.1X supplicant took too long to authenticate
Hint: use 'journalctl -xe NM_CONNECTION=ebb00c78-7fda-47be-8546-33ec08904fd7 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=DISCONNECTED
$ ping -c3 10.43.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2026ms
--- supplicant
Sep 15 09:25:57.103087 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:25:57.272039 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:26:10.558201 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:26:10.702751 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
--- firmware SET_SSID
Sep 15 09:25:57.275846 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:40:bf
Sep 15 09:25:57.275976 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:26:10.703941 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:40:bf
Sep 15 09:26:10.704113 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
=== b-ch36-run2 end 2026-09-15T09:26:29+00:00
--- coordinator
=== b-ch36-run3 start 2026-09-15T09:26:30+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	5180	-69	[WPS][ESS]	e87diag-open
2026-09-15T09:26:39+00:00 $ nmcli connection up e87diag-open-sta
Error: Connection activation failed: 802.1X supplicant took too long to authenticate
Hint: use 'journalctl -xe NM_CONNECTION=ebb00c78-7fda-47be-8546-33ec08904fd7 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=DISCONNECTED
$ ping -c3 10.43.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2056ms
--- supplicant
Sep 15 09:26:40.240895 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:26:40.386876 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:26:53.673988 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:26:53.807802 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
--- firmware SET_SSID
Sep 15 09:26:40.387907 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:40:bf
Sep 15 09:26:40.388058 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:26:53.807749 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:40:bf
Sep 15 09:26:53.807881 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
=== b-ch36-run3 end 2026-09-15T09:27:12+00:00
--- coordinator
```

### Channel 149

```text
##### TEST B ch149 (ribbon disconnected), local 2026-09-15T09:27:26Z
2026-09-15T09:27:27+00:00 $ nmcli connection up e87diag-open-ap
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/28)
bssid=88:a2:9e:ff:6d:38
freq=5745
ssid=e87diag-open
mode=AP
wpa_state=COMPLETED
ip_address=10.43.0.1
--- console flushed scan (5 GHz)
boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9 2026-09-15T09:27:33+00:00
scan attempts: 1
bssid / frequency / signal level / flags / ssid
d0:21:f9:bf:a2:ce	5180	-56	[WPA2-PSK+SAE-CCMP][ESS]	Aileoze_5
38:a6:ce:86:b8:d5	5180	-71	[WPA2-PSK-CCMP][WPS][ESS]	SKYEA800
20:47:ed:a8:43:23	5180	-73	[WPA2-PSK-CCMP][WPS-AUTH][ESS]	SKY00973
88:a2:9e:ff:6d:38	5745	-67	[WPS][ESS]	e87diag-open
=== b-ch149-run1 start 2026-09-15T09:27:40+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 2
88:a2:9e:ff:6d:38	5745	-67	[WPS][ESS]	e87diag-open
2026-09-15T09:27:53+00:00 $ nmcli connection up e87diag-open-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/10)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=5745
ssid=e87diag-open
key_mgmt=NONE
wpa_state=COMPLETED
ip_address=10.43.0.2
$ ping -c3 10.43.0.1
64 bytes from 10.43.0.1: icmp_seq=1 ttl=64 time=11.6 ms
64 bytes from 10.43.0.1: icmp_seq=2 ttl=64 time=15.8 ms
3 packets transmitted, 2 received, 33.3333% packet loss, time 2004ms
--- supplicant
Sep 15 09:27:54.064704 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:27:55.079301 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:27:55.079809 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
Sep 15 09:27:55.075773 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:27:55.075934 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
=== b-ch149-run1 end 2026-09-15T09:28:02+00:00
--- coordinator
Sep 15 09:27:54.165490 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:01.612149 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== b-ch149-run2 start 2026-09-15T09:28:02+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	5745	-67	[WPS][ESS]	e87diag-open
2026-09-15T09:28:08+00:00 $ nmcli connection up e87diag-open-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/11)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=5745
ssid=e87diag-open
key_mgmt=NONE
wpa_state=COMPLETED
ip_address=10.43.0.2
$ ping -c3 10.43.0.1
64 bytes from 10.43.0.1: icmp_seq=1 ttl=64 time=10.0 ms
64 bytes from 10.43.0.1: icmp_seq=3 ttl=64 time=13.9 ms
3 packets transmitted, 2 received, 33.3333% packet loss, time 2015ms
--- supplicant
Sep 15 09:28:09.591731 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:09.952035 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:28:13.306036 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:13.669217 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:28:17.403063 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:17.506611 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:28:17.507053 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
Sep 15 09:28:09.955803 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:27:d1:d4:47:cd
Sep 15 09:28:09.955929 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:13.671789 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:10:18:02:00:00
Sep 15 09:28:13.671882 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:17.503827 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:28:17.503975 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
=== b-ch149-run2 end 2026-09-15T09:28:24+00:00
--- coordinator
Sep 15 09:28:17.483812 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:24.136744 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== b-ch149-run3 start 2026-09-15T09:28:25+00:00 boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9
scan attempts: 1
88:a2:9e:ff:6d:38	5745	-67	[WPS][ESS]	e87diag-open
2026-09-15T09:28:31+00:00 $ nmcli connection up e87diag-open-sta
Error: Connection activation failed: 802.1X supplicant took too long to authenticate
Hint: use 'journalctl -xe NM_CONNECTION=ebb00c78-7fda-47be-8546-33ec08904fd7 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=INACTIVE
$ ping -c3 10.43.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2049ms
--- supplicant
Sep 15 09:28:35.827075 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:36.193182 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:28:39.938523 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:40.301215 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:28:44.570479 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:44.932060 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
Sep 15 09:28:55.219732 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: Trying to associate with SSID 'e87diag-open'
Sep 15 09:28:55.627237 e87-console-ef27d0966bdd wpa_supplicant[465]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=88:a2:9e:ff:6d:38 status_code=16
--- firmware SET_SSID
Sep 15 09:28:32.475843 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:27:d1:d4:47:cd
Sep 15 09:28:32.475984 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:36.195821 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:10:18:02:00:00
Sep 15 09:28:36.195950 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:40.303860 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:27:d1:d4:47:cd
Sep 15 09:28:40.303969 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:44.935821 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:27:d1:d4:47:cd
Sep 15 09:28:44.935948 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:28:55.627925 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 10:27:d1:d4:47:cd
Sep 15 09:28:55.628086 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
=== b-ch149-run3 end 2026-09-15T09:29:06+00:00
--- coordinator
Sep 15 09:28:24.136744 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:35.909909 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:40.007861 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:55.340007 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
```

Channel 36 reference: the original session's display-attached scan listed `Aileoze_5` -48, `SKYEA800` -68 and `SKY00973` -73 on 5180 MHz. This session's ribbon-off channel 36 scan listed `Aileoze_5` -49, `SKYEA800` -69 and `SKY00973` -70. The ribbon-off channel 149 scan listed the same three at -56, -71 and -73. The same three networks appeared at similar levels in every phase 2 (ribbon-on) census scan.

## Transition 1

```text
##### coordinator back to prod AP ch1 for phase 2, local 2026-09-15T09:29:21Z
ssid=e87diag-prod
2026-09-15T09:29:21+00:00 $ nmcli connection up e87diag-prod-ap
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
##### TRANSITION 1: console poweroff requested (ribbon disconnected -> reattach), local 2026-09-15T09:29:26Z
last boot_id=6b27065f-e826-4bd5-b054-e3a4c68820f9 2026-09-15T09:29:27+00:00
Connection 'e87diag-open-sta' (ebb00c78-7fda-47be-8546-33ec08904fd7) successfully deleted.
Connection 'e87diag-prod-sta' (92541397-a29e-3328-9284-3d128ec28407) successfully deleted.
Running timer as unit: run-p2322-i2323.timer
Will run service as unit: run-p2322-i2323.service
poweroff scheduled
```

## Phase 2: ribbon attached (boot `ba7121cc`)

### State

```text
##### PHASE 2 (ribbon reattached) state check, local 2026-09-15T09:32:51Z; Aidan reports power on ~09:33 UTC
2026-09-15T09:30:22+00:00
boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868
booted=2026-09-15 09:29:38
 -2 4a7cd3ba4c374f14b0d7e24364e9a178 Tue 2026-09-15 08:40:04 UTC Tue 2026-09-15 09:14:29 UTC
 -1 6b27065fe8264bd5b054e3a4c68820f9 Tue 2026-09-15 09:16:25 UTC Tue 2026-09-15 09:29:41 UTC
  0 ba7121cc1b9f494d9ee7ce32b0380868 Tue 2026-09-15 09:29:42 UTC Tue 2026-09-15 09:30:22 UTC
card1-DSI-1 status=connected enabled=enabled mode=800x480
card1-HDMI-A-1 status=disconnected enabled=disabled mode=
card1-HDMI-A-2 status=disconnected enabled=disabled mode=
card1-Writeback-1 status=unknown enabled=disabled mode=
active
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
debug=0
ls: cannot access '/tmp/sta.sh': No such file or directory
ls: cannot access '/tmp/census.sh': No such file or directory
```

The `ls` errors show that `/tmp` was cleared by the reboot. The scripts were copied again before the runs.

### Channel 1 joins

The coordinator journal window for these runs started 5 minutes before each run, to cover the console clock offset. Its lines up to 09:29:21 are from Test B and the phase 2 AP reset, not from these runs. No `AP-STA-CONNECTED` occurred after 09:29:21.

```text
##### PHASE 2 (ribbon attached) Test A ch1 prod joins, local 2026-09-15T09:33:07Z
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
$ /run/NetworkManager/system-connections/e87diag-prod-sta.nmconnection (psk redacted)
[connection]
id=e87diag-prod-sta
type=wifi
interface-name=wlan0
autoconnect=false

[wifi]
mode=infrastructure
ssid=e87diag-prod

[wifi-security]
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
psk=<redacted>

[ipv4]
address1=10.42.0.2/24
method=manual
never-default=true
ignore-auto-dns=true

[ipv6]
method=disabled
=== p2-ch1-run1 start 2026-09-15T09:33:08+00:00 boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868
scan attempts: 6
2026-09-15T09:33:45+00:00 $ nmcli connection up e87diag-prod-sta
Error: Connection activation failed: The Wi-Fi network could not be found
Hint: use 'journalctl -xe NM_CONNECTION=92541397-a29e-3328-9284-3d128ec28407 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=DISCONNECTED
$ ping -c3 10.42.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2027ms
--- supplicant
--- firmware SET_SSID
=== p2-ch1-run1 end 2026-09-15T09:34:18+00:00
--- coordinator (since 2026-09-15 09:28:07)
Sep 15 09:28:17.483812 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:24.136744 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:35.909909 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:40.007861 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:28:55.340007 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:29:21.885681 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p2-ch1-run2 start 2026-09-15T09:34:19+00:00 boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868
scan attempts: 6
2026-09-15T09:34:57+00:00 $ nmcli connection up e87diag-prod-sta
Error: Connection activation failed: The Wi-Fi network could not be found
Hint: use 'journalctl -xe NM_CONNECTION=92541397-a29e-3328-9284-3d128ec28407 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=DISCONNECTED
$ ping -c3 10.42.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2030ms
--- supplicant
--- firmware SET_SSID
=== p2-ch1-run2 end 2026-09-15T09:35:30+00:00
--- coordinator (since 2026-09-15 09:29:18)
Sep 15 09:29:21.885681 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p2-ch1-run3 start 2026-09-15T09:35:31+00:00 boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868
scan attempts: 2
88:a2:9e:ff:6d:38	2412	-62	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:35:43+00:00 $ nmcli connection up e87diag-prod-sta
Error: Connection activation failed: Secrets were required, but not provided
Hint: use 'journalctl -xe NM_CONNECTION=92541397-a29e-3328-9284-3d128ec28407 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=SCANNING
$ ping -c3 10.42.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2040ms
--- supplicant
Sep 15 09:35:47.422296 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:35:47.915543 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
Sep 15 09:35:51.399193 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:35:51.807573 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
Sep 15 09:35:55.794178 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:35:56.412315 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
Sep 15 09:36:06.399853 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:36:07.059463 e87-console-ef27d0966bdd wpa_supplicant[484]: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
--- firmware SET_SSID
Sep 15 09:35:44.384042 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:00:00:00:00
Sep 15 09:35:44.384215 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 3 reason 0
Sep 15 09:35:47.916409 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 48:48:48:48:40:3e
Sep 15 09:35:47.916536 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:35:51.808263 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:10:18:02:00:00
Sep 15 09:35:51.808380 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:35:56.416073 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:fd:ff:22:00
Sep 15 09:35:56.416180 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
Sep 15 09:36:07.060209 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 00:00:f8:ff:20:00
Sep 15 09:36:07.060323 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 1 reason 0
=== p2-ch1-run3 end 2026-09-15T09:36:17+00:00
--- coordinator (since 2026-09-15 09:30:30)
```

### Census

```text
=== census phase2-ribbon-on start 2026-09-15T09:36:25+00:00 boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868
card1-DSI-1 status=connected enabled=enabled
scan 1 09:36:32: total=4 2.4GHz=1 5GHz=3 weakest=-73
    2457 -73 30:68:93:22:96:72 SHELL D90CB7
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -69 38:a6:ce:86:b8:d5 SKYEA800
    5180 -56 d0:21:f9:bf:a2:ce Aileoze_5
scan 2 09:36:41: total=5 2.4GHz=2 5GHz=3 weakest=-73
    2412 -56 d0:21:f9:bf:a2:cd Aileoze_2.4
    2457 -72 30:68:93:22:96:72 SHELL D90CB7
    5180 -73 20:47:ed:a8:43:23 SKY00973
    5180 -68 38:a6:ce:86:b8:d5 SKYEA800
    5180 -55 d0:21:f9:bf:a2:ce Aileoze_5
scan 3 09:36:48: total=3 2.4GHz=0 5GHz=3 weakest=-73
    5180 -73 20:47:ed:a8:43:23 SKY00973
    5180 -68 38:a6:ce:86:b8:d5 SKYEA800
    5180 -58 d0:21:f9:bf:a2:ce Aileoze_5
scan 4 09:36:55: total=5 2.4GHz=2 5GHz=3 weakest=-74
    2412 -52 d0:21:f9:bf:a2:cd Aileoze_2.4
    2457 -74 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -74 20:47:ed:a8:43:23 SKY00973
    5180 -68 38:a6:ce:86:b8:d5 SKYEA800
    5180 -57 d0:21:f9:bf:a2:ce Aileoze_5
scan 5 09:37:02: total=5 2.4GHz=2 5GHz=3 weakest=-73
    2412 -56 d0:21:f9:bf:a2:cd Aileoze_2.4
    2457 -73 30:68:93:22:96:72 SHELL D90CB7
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -67 38:a6:ce:86:b8:d5 SKYEA800
    5180 -51 d0:21:f9:bf:a2:ce Aileoze_5
scan 6 09:37:10: total=3 2.4GHz=0 5GHz=3 weakest=-70
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -47 d0:21:f9:bf:a2:ce Aileoze_5
scan 7 09:37:17: total=4 2.4GHz=1 5GHz=3 weakest=-70
    2412 -61 d0:21:f9:bf:a2:cd Aileoze_2.4
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -67 38:a6:ce:86:b8:d5 SKYEA800
    5180 -47 d0:21:f9:bf:a2:ce Aileoze_5
scan 8 09:37:24: total=3 2.4GHz=0 5GHz=3 weakest=-70
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -47 d0:21:f9:bf:a2:ce Aileoze_5
scan 9 09:37:31: total=3 2.4GHz=0 5GHz=3 weakest=-70
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -67 38:a6:ce:86:b8:d5 SKYEA800
    5180 -47 d0:21:f9:bf:a2:ce Aileoze_5
scan 10 09:37:38: total=5 2.4GHz=2 5GHz=3 weakest=-75
    2412 -61 d0:21:f9:bf:a2:cd Aileoze_2.4
    2457 -75 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -70 20:47:ed:a8:43:23 SKY00973
    5180 -62 38:a6:ce:86:b8:d5 SKYEA800
    5180 -48 d0:21:f9:bf:a2:ce Aileoze_5
=== census phase2-ribbon-on end 2026-09-15T09:37:38+00:00
```

## Transition 2

```text
##### TRANSITION 2: console poweroff requested (ribbon attached -> disconnect), local 2026-09-15T09:37:52Z
last boot_id=ba7121cc-1b9f-494d-9ee7-ce32b0380868 2026-09-15T09:37:53+00:00
Connection 'e87diag-prod-sta' (92541397-a29e-3328-9284-3d128ec28407) successfully deleted.
Running timer as unit: run-p1599-i1600.timer
Will run service as unit: run-p1599-i1600.service
poweroff scheduled
```

## Phase 3: ribbon disconnected (boot `b2886ac3`)

### State

```text
##### PHASE 3 (ribbon disconnected again) state check, local 2026-09-15T09:40:14Z; Aidan reports power on ~09:39 UTC
2026-09-15T09:40:14+00:00
boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
booted=2026-09-15 09:39:19
 -2 6b27065fe8264bd5b054e3a4c68820f9 Tue 2026-09-15 09:16:25 UTC Tue 2026-09-15 09:29:41 UTC
 -1 ba7121cc1b9f494d9ee7ce32b0380868 Tue 2026-09-15 09:29:42 UTC Tue 2026-09-15 09:38:05 UTC
  0 b2886ac352d1461ba0939f8d45e2f732 Tue 2026-09-15 09:38:06 UTC Tue 2026-09-15 09:40:14 UTC
card1-HDMI-A-1 status=disconnected enabled=disabled
card1-HDMI-A-2 status=disconnected enabled=disabled
card1-Writeback-1 status=unknown enabled=disabled
NTPSynchronized=yes
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
debug=0
```

### Channel 1 joins

```text
##### PHASE 3 (ribbon disconnected) Test A ch1 prod joins, local 2026-09-15T09:40:25Z
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
$ /run/NetworkManager/system-connections/e87diag-prod-sta.nmconnection (psk redacted)
[connection]
id=e87diag-prod-sta
type=wifi
interface-name=wlan0
autoconnect=false

[wifi]
mode=infrastructure
ssid=e87diag-prod

[wifi-security]
key-mgmt=wpa-psk
proto=rsn
pairwise=ccmp
group=ccmp
pmf=3
psk=<redacted>

[ipv4]
address1=10.42.0.2/24
method=manual
never-default=true
ignore-auto-dns=true

[ipv6]
method=disabled
=== p3-ch1-run1 start 2026-09-15T09:40:26+00:00 boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-62	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:40:32+00:00 $ nmcli connection up e87diag-prod-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/3)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping -c3 10.42.0.1
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=18.9 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=14.5 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=7.67 ms
3 packets transmitted, 3 received, 0% packet loss, time 2001ms
--- supplicant
Sep 15 09:40:35.211076 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:40:38.106623 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:40:38.106700 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
Sep 15 09:40:38.084830 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:40:38.085043 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
=== p3-ch1-run1 end 2026-09-15T09:40:44+00:00
--- coordinator (since 2026-09-15 09:40:25)
Sep 15 09:40:35.348956 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:40:35.349860 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
Sep 15 09:40:43.865184 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p3-ch1-run2 start 2026-09-15T09:40:45+00:00 boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-69	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:40:51+00:00 $ nmcli connection up e87diag-prod-sta
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/4)
$ wpa_cli status
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87diag-prod
key_mgmt=WPA2-PSK-SHA256
pmf=2
wpa_state=COMPLETED
ip_address=10.42.0.2
$ ping -c3 10.42.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2044ms
--- supplicant
Sep 15 09:40:54.194753 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: Trying to associate with SSID 'e87diag-prod'
Sep 15 09:40:54.685111 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: Associated with 88:a2:9e:ff:6d:38
Sep 15 09:40:54.685224 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
--- firmware SET_SSID
Sep 15 09:40:54.680699 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker event SET_SSID (0:0) ifidx 0 bsscfg 0 addr 88:a2:9e:ff:6d:38
Sep 15 09:40:54.680864 e87-console-ef27d0966bdd kernel: brcmfmac: brcmf_fweh_event_worker   version 2 flags 0 status 0 reason 0
=== p3-ch1-run2 end 2026-09-15T09:41:02+00:00
--- coordinator (since 2026-09-15 09:40:44)
Sep 15 09:40:54.351668 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-CONNECTED d8:3a:dd:3c:54:f6
Sep 15 09:40:54.352421 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: EAPOL-4WAY-HS-COMPLETED d8:3a:dd:3c:54:f6
Sep 15 09:41:02.265185 e87-coordinator-1069df5e6c91 wpa_supplicant[454]: wlan0: AP-STA-DISCONNECTED d8:3a:dd:3c:54:f6
=== p3-ch1-run3 start 2026-09-15T09:41:03+00:00 boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
scan attempts: 1
88:a2:9e:ff:6d:38	2412	-67	[WPA2-PSK-SHA256-CCMP][WPS][ESS]	e87diag-prod
2026-09-15T09:41:09+00:00 $ nmcli connection up e87diag-prod-sta
Error: Connection activation failed: The Wi-Fi network could not be found
Hint: use 'journalctl -xe NM_CONNECTION=92541397-a29e-3328-9284-3d128ec28407 + NM_DEVICE=wlan0' to get more details.
$ wpa_cli status
wpa_state=DISCONNECTED
$ ping -c3 10.42.0.1
3 packets transmitted, 0 received, 100% packet loss, time 2045ms
--- supplicant
--- firmware SET_SSID
=== p3-ch1-run3 end 2026-09-15T09:41:44+00:00
--- coordinator (since 2026-09-15 09:41:03)
```

In run 2, NetworkManager reported `Activation: successful, device activated` at 09:40:54.92, but no ping reply arrived before the script disconnected at 09:41:02. In run 3, NetworkManager's own pre-connect scan did not find the AP, so no association was attempted and no `SET_SSID` event occurred.

### Census

```text
=== census phase3-ribbon-off start 2026-09-15T09:41:45+00:00 boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
card1-DSI-1 absent
scan 1 09:41:53: total=10 2.4GHz=7 5GHz=3 weakest=-83
    2412 -58 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -83 6a:b6:87:89:e8:8a EE WiFi
    2437 -82 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -82 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -79 36:68:93:22:96:72 
    2457 -79 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -80 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -51 d0:21:f9:bf:a2:ce Aileoze_5
scan 2 09:42:00: total=10 2.4GHz=7 5GHz=3 weakest=-81
    2412 -51 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -72 6a:b6:87:89:e8:8a EE WiFi
    2437 -81 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -79 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -75 30:68:93:22:96:72 SHELL D90CB7
    2457 -80 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -81 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -65 38:a6:ce:86:b8:d5 SKYEA800
    5180 -51 d0:21:f9:bf:a2:ce Aileoze_5
scan 3 09:42:07: total=8 2.4GHz=5 5GHz=3 weakest=-82
    2412 -51 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -82 6a:b6:87:89:e8:8a EE WiFi
    2437 -78 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -78 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2462 -81 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 4 09:42:14: total=6 2.4GHz=3 5GHz=3 weakest=-81
    2412 -55 d0:21:f9:bf:a2:cd Aileoze_2.4
    2457 -77 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -81 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 5 09:42:21: total=12 2.4GHz=9 5GHz=3 weakest=-83
    2412 -64 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -47 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -80 6a:b6:87:89:e8:8a EE WiFi
    2437 -78 6a:b6:87:89:e8:8d \x00\x00\x00\x00\x00\x00\x00\x00\x00
    2437 -74 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -83 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -79 30:68:93:22:96:72 SHELL D90CB7
    2457 -80 36:68:93:22:96:72 
    2457 -77 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -49 d0:21:f9:bf:a2:ce Aileoze_5
scan 6 09:42:28: total=7 2.4GHz=4 5GHz=3 weakest=-83
    2412 -48 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -83 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -80 30:68:93:22:96:72 SHELL D90CB7
    2457 -76 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -65 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 7 09:42:35: total=10 2.4GHz=7 5GHz=3 weakest=-85
    2412 -69 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -46 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -81 6a:b6:87:89:e8:8a EE WiFi
    2437 -83 6a:b6:87:89:e8:8d \x00\x00\x00\x00\x00\x00\x00\x00\x00
    2437 -83 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -85 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -77 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -72 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 8 09:42:42: total=11 2.4GHz=8 5GHz=3 weakest=-85
    2412 -66 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -46 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -84 6a:b6:87:89:e8:8a EE WiFi
    2437 -82 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -71 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -80 30:68:93:22:96:72 SHELL D90CB7
    2457 -80 36:68:93:22:96:72 
    2462 -85 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -73 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 9 09:42:49: total=10 2.4GHz=7 5GHz=3 weakest=-83
    2412 -66 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -46 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -83 6a:b6:87:89:e8:8a EE WiFi
    2437 -82 6a:b6:87:89:e8:8d \x00\x00\x00\x00\x00\x00\x00\x00\x00
    2437 -81 ac:b6:87:89:e8:89 BT-FSF66R
    2457 -82 30:68:93:22:96:72 SHELL D90CB7
    2457 -78 3e:68:93:22:96:72 SHELL D90CB7_Guest
    5180 -73 20:47:ed:a8:43:23 SKY00973
    5180 -65 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
scan 10 09:42:57: total=12 2.4GHz=9 5GHz=3 weakest=-83
    2412 -70 88:a2:9e:ff:6d:38 e87diag-prod
    2412 -49 d0:21:f9:bf:a2:cd Aileoze_2.4
    2437 -82 6a:b6:87:89:e8:8a EE WiFi
    2437 -82 6a:b6:87:89:e8:8d \x00\x00\x00\x00\x00\x00\x00\x00\x00
    2437 -77 ac:b6:87:89:e8:89 BT-FSF66R
    2437 -74 b0:3e:51:71:f8:36 SKYBU8GG 2.4
    2457 -80 30:68:93:22:96:72 SHELL D90CB7
    2457 -77 3e:68:93:22:96:72 SHELL D90CB7_Guest
    2462 -83 3c:9e:c7:9d:e1:f2 SKYJCRY2
    5180 -71 20:47:ed:a8:43:23 SKY00973
    5180 -66 38:a6:ce:86:b8:d5 SKYEA800
    5180 -50 d0:21:f9:bf:a2:ce Aileoze_5
=== census phase3-ribbon-off end 2026-09-15T09:42:57+00:00
```

## Restore

```text
##### RESTORE, local 2026-09-15T09:43:24Z
--- console
+ sudo nmcli connection delete e87diag-prod-sta e87diag-open-sta
Error: unknown connection 'e87diag-open-sta'.
Connection 'e87diag-prod-sta' (92541397-a29e-3328-9284-3d128ec28407) successfully deleted.
Error: cannot delete unknown connection(s): 'e87diag-open-sta'.
+ sudo ls /run/NetworkManager/system-connections/
Wired connection 1.nmconnection
lo.nmconnection
+ rm -f /tmp/sta.sh /tmp/census.sh
+ sudo sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
5a1d59254b9076057c80abc4a7e7548474a77527fd99c0380ff891d0ca294b95  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
+ sudo cat /sys/module/brcmfmac/parameters/debug
0
++ cat /proc/sys/kernel/random/boot_id
boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
+ echo boot_id=b2886ac3-52d1-461b-a093-9f8d45e2f732
+ ls /sys/class/drm/
+ grep -c DSI
0
+ ls /tmp
systemd-private-b2886ac352d1461ba0939f8d45e2f732-e87canbus-console.service-o8f0jB
systemd-private-b2886ac352d1461ba0939f8d45e2f732-systemd-logind.service-uQWThz
--- coordinator
+ sudo nmcli connection down e87diag-prod-ap
Connection 'e87diag-prod-ap' successfully deactivated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/29)
+ sudo nmcli connection delete e87diag-prod-ap e87diag-open-ap
Error: unknown connection 'e87diag-open-ap'.
Connection 'e87diag-prod-ap' (f234965e-5442-3b90-8ab7-5eb090ab4fd3) successfully deleted.
Error: cannot delete unknown connection(s): 'e87diag-open-ap'.
Wired connection 1.nmconnection
lo.nmconnection
+ sudo ls /run/NetworkManager/system-connections/
+ sudo nmcli connection up e87canbus-coordinator-wifi
Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/30)
+ sleep 3
+ sudo wpa_cli -i wlan0 status
+ grep -E '^(freq|ssid|key_mgmt|wpa_state)='
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
+ rm -f /tmp/ap.sh
+ sudo sha256sum /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
0292ed90aec7521bb005f90ef8076ead1473abaf9d8bcc372f264f3a672b45ec  /etc/NetworkManager/system-connections/e87canbus-wifi.nmconnection
+ sudo cat /sys/module/brcmfmac/parameters/debug
0
+ ls /tmp
systemd-private-58dae3987d4244229b5d1c7de37b8b33-e87canbus-controller.service-Xw6C30
systemd-private-58dae3987d4244229b5d1c7de37b8b33-e87canbus-dnsmasq.service-OIfRsq
systemd-private-58dae3987d4244229b5d1c7de37b8b33-systemd-logind.service-FZJO1E
--- console autoconnect check 2026-09-15T09:43:45Z
wpa_state=DISCONNECTED
3 packets transmitted, 0 received, 100% packet loss, time 2027ms
--- console autoconnect recheck 2026-09-15T09:44:04Z (waited 0s)
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.2
NAME                    DEVICE  STATE     
Wired connection 1      end0    activated 
e87canbus-console-wifi  wlan0   activated 
lo                      lo      activated 
64 bytes from 10.42.0.1: icmp_seq=1 ttl=64 time=11.4 ms
64 bytes from 10.42.0.1: icmp_seq=2 ttl=64 time=10.9 ms
64 bytes from 10.42.0.1: icmp_seq=3 ttl=64 time=8.03 ms
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
Sep 15 09:40:54.685224 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
Sep 15 09:41:02.259210 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: CTRL-EVENT-DISCONNECTED bssid=88:a2:9e:ff:6d:38 reason=3 locally_generated=1
Sep 15 09:43:54.539316 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: Trying to associate with SSID 'e87canbus-jv4xu4p3ip2r'
Sep 15 09:43:54.633778 e87-console-ef27d0966bdd wpa_supplicant[467]: wlan0: CTRL-EVENT-CONNECTED - Connection to 88:a2:9e:ff:6d:38 completed [id=0 id_str=]
```

Both keyfile hashes match the values recorded in [`2827f7e-pmf-akm-test.md`](2827f7e-pmf-akm-test.md) (`0292ed90…` coordinator, `5a1d5925…` console). `debug` reads `0` on both devices. No in-memory profiles or diagnostic files remain on either device. The DSI ribbon was left **disconnected**, and the console remains in boot `b2886ac3`.

The cards remain diagnostic. Final gate evidence must come from freshly provisioned clean cards.
