# Candidate 2827f7e physical gate report

Date: 2026-09-14  
Candidate: `2827f7eaa2a69f5c1daf26910c4fe813a974b8e3`  
Deployment profile: `bench`  
Installation ID: `jv4xu4p3ip2r6ngwxlbgv3nwpx6wx7yeeufe5kerapegyej44c4q`

## Result

The coordinator image passes its complete physical image check. The console boots into the kiosk and remains stable, but the physical gate fails because the console cannot associate with the coordinator Wi-Fi network.

Both devices conclusively load Debian's `firmware-brcm80211` version `20250410-2` and Broadcom firmware `7.45.234`. The package-origin change in candidate 2827f7e therefore took effect, but it does not resolve this Pi-to-Pi association failure.

## Exact images provisioned

### Coordinator

- Image: `artifacts/images/coordinator/e87-coordinator_2026-09-14_1836Z_2827f7e.img`
- Image SHA-256: `8736561f454f7864e8b798cae7e425fce0e22509b5ee1c4708711fb5333b615f`
- Hostname: `e87-coordinator-1069df5e6c91`
- Device ID: `1069df5e-6c91-4acc-bb51-8b9fb0b0d2a0`
- Application SHA-256: `2f6ab6ddee388f202016f9f4b645088a3d8078bce8b1e56664e54117e78341c4`
- Provisioning SHA-256: `a548af00355042264b21da238950438abfbd78712a81ed7a02f1988d4a7dfc56`
- SSH ED25519 host-key fingerprint: `SHA256:wEoKt/g0SUA9WS1NAvw61dLUKTKynx9zWpNhWqgG9io`

### Console

- Image: `artifacts/images/console/e87-console_2026-09-14_1843Z_2827f7e.img`
- Image SHA-256: `335ed54ad480ab118a8b9b31ddd62c582e49ea31c46bb72184d0802815bec867`
- Hostname: `e87-console-ef27d0966bdd`
- Device ID: `ef27d096-6bdd-4f9e-89d3-962750797b8a`
- Application SHA-256: `208c19d935adeb0e947fa8904e0cfffdbb57c3d2249d238a251fbdff75c589f3`
- Provisioning SHA-256: `6a889329ae63013822e954b8a1270e010db1e7850e94c4449241f2ed97a9c9ec`
- SSH ED25519 host-key fingerprint: `SHA256:beb1A7dMnqYI//vT7LkQWbRgXpQXJjs9GFMiCBuFIv8`

Both manifests report the exact candidate commit and `git_dirty=false`. Both cards were freshly provisioned from these images.

## Image-check results

The checker was streamed over SSH from the exact candidate checkout, so running it did not modify either card.

- Coordinator: every coordinator check passed.
- Console: every console check passed except `WPA2-RSN console Wi-Fi active at 10.42.0.2`.
- The console kiosk rendered and remained stable.
- Bench CAN configuration passed, including 100 kbit/s and listen-only disabled.
- Console services, Chromium certificate database and selection policy, Cage/Chromium, DRM, touchscreen, and provisioning checks passed.

## Requested kernel and firmware evidence

Both devices returned:

```text
$ uname -r
6.18.39+rpt-rpi-v8

$ dpkg-query -W firmware-brcm80211
firmware-brcm80211    20250410-2
```

The coordinator boot log returned:

```text
Sep 14 18:36:58 pi4-ruernb kernel: brcmfmac mmc1:0001:1: Direct firmware load for brcm/brcmfmac43455-sdio.raspberrypi,4-model-b.bin failed with error -2
Sep 14 18:36:58 pi4-ruernb kernel: brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM4345/6 wl0: Apr 15 2021 03:03:20 version 7.45.234 (4ca95bb CY) FWID 01-996384e2
```

The console's initial boot returned the same firmware identity:

```text
Sep 14 18:44:03 pi4-xtflfb kernel: brcmfmac mmc1:0001:1: Direct firmware load for brcm/brcmfmac43455-sdio.raspberrypi,4-model-b.bin failed with error -2
Sep 14 18:44:03 pi4-xtflfb kernel: brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM4345/6 wl0: Apr 15 2021 03:03:20 version 7.45.234 (4ca95bb CY) FWID 01-996384e2
```

The missing board-specific `.bin` is followed by successful loading of the generic 7.45.234 blob on both devices.

## Wi-Fi state and failure signature

The coordinator AP is active with:

```text
bssid=88:a2:9e:ff:6d:38
freq=2412
ssid=e87canbus-jv4xu4p3ip2r
mode=AP
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
ip_address=10.42.0.1
```

The console sees that BSS on channel 1 at 2412 MHz with full reported signal. Its repeated connection failure remains:

```text
wlan0: Trying to associate with 88:a2:9e:ff:6d:38
wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
```

Earlier cfg80211 tracing on the physical console showed the scan result with the correct AP BSSID, followed by an accepted nl80211 connect request and then the local status-16 result. No authentication or association callback appeared. The coordinator observed no corresponding station event. This places the failure on the console before an authentication exchange reaches the AP.

## Additional diagnostic experiments

These experiments were runtime-only. The temporary configuration was removed and the normal modules and settings were restored afterward.

1. PMF required, optional, and disabled all produced the same failure.
2. Disabling Wi-Fi power saving produced the same failure.
3. Bypassing NetworkManager with direct `wpa_supplicant` produced the same failure.
4. The console can associate with ordinary 2.4 GHz access points, including `Aileoze_5` and `Aileoze_2.4`.
5. A Mac can associate with the coordinator AP and complete its WPA handshake.
6. Rebooting did not alter the failure.
7. Candidate 2827f7e removed Raspberry Pi package-owned `/usr/lib/modprobe.d/rpi-brcmfmac.conf`, whose content was:

   ```text
   options brcmfmac roamoff=1 feature_disable=0x282000
   ```

   The unchanged kernel module supports both parameters. Reloading the driver temporarily with those exact options still produced the same local status-16 failure, ruling their omission out as the direct cause.

## Regulatory evidence

Both devices run with:

```text
ieee80211_regdom=00
options cfg80211 ieee80211_regdom=00
```

The image contains `wireless-regdb` but not the `iw` executable. Equivalent live evidence was collected through cfg80211 sysfs, NetworkManager, and `wpa_cli`.

Because the AP selected channel 1 at 2412 MHz and the console receives it at full signal, world-domain no-initiate-radiation restrictions do not account for this failure. An explicit country, band, and channel may improve deployment determinism, but current evidence does not support presenting that as the status-16 fix.

## Conclusion and next decision

Candidate 2827f7e is a failed console physical gate despite a passing coordinator and stable kiosk. It proves that Debian firmware 7.45.234 is installed and active on both Pis, but the local pre-authentication status-16 failure persists.

The next high-value investigation is a controlled kernel/firmware matrix, particularly Debian firmware with a non-Raspberry-Pi kernel or an older Raspberry Pi kernel, or driver-level instrumentation of the brcmfmac connect path. PMF/RSN AP interoperability remains worth checking only after a candidate progresses beyond association into the four-way handshake.
