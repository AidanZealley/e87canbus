# BCM4345/6 Pi-to-Pi Wi-Fi research brief

Date: 2026-09-14

## Research objective

Explain why a Raspberry Pi 4 console using `brcmfmac` cannot initiate association with a Raspberry Pi 4 NetworkManager access point, even after moving both devices from Raspberry Pi firmware 7.45.265 to Debian firmware 7.45.234.

The useful deliverable is a technically grounded next experiment or minimal image change. Please distinguish evidence that applies to pre-authentication association from issues that can occur later during the WPA four-way handshake.

## Hardware and software

- Two Raspberry Pi 4 devices with BCM4345/6 Wi-Fi.
- Kernel on both: `6.18.39+rpt-rpi-v8` from `linux-image-rpi-v8 1:6.18.39-1+rpt1`.
- Firmware package on both: Debian `firmware-brcm80211 20250410-2`.
- Loaded firmware on both: `7.45.234 (4ca95bb CY)`, FWID `01-996384e2`.
- NetworkManager: `1.52.1-1+rpt4`.
- wpa_supplicant: `2:2.10-24`.
- NetworkManager is the only network owner.
- Coordinator AP: WPA2-RSN, CCMP, WPA2-PSK-SHA256, required PMF, forwarding disabled.
- Console station: matching WPA2-RSN, CCMP, WPA2-PSK-SHA256, required PMF.

## Reproducible failure

The coordinator AP is operational at `10.42.0.1`:

```text
bssid=88:a2:9e:ff:6d:38
freq=2412
mode=AP
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=WPA2-PSK-SHA256
wpa_state=COMPLETED
```

The console detects the correct BSS at full signal, attempts to associate, and approximately 0.4 seconds later reports:

```text
CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00 status_code=16
```

cfg80211 tracing shows the BSS discovered with the correct BSSID and the nl80211 connect request accepted. No authentication or association callback follows before the status-16 failure. The coordinator sees no station event. The current working interpretation is that the console firmware/driver generates the failure locally before transmitting a usable authentication frame.

## What has already been ruled out experimentally

- Incorrect PSK or basic AP failure: a Mac joins the coordinator and completes the handshake.
- General console radio failure: the console joins ordinary 2.4 GHz access points.
- NetworkManager-specific behavior: direct `wpa_supplicant` has the same result.
- PMF setting at the current failure stage: required, optional, and disabled all have the same pre-authentication result.
- Wi-Fi power saving: disabling it does not help.
- Stale transient state: rebooting does not help.
- Missing Raspberry Pi module defaults: loading `brcmfmac` with `roamoff=1 feature_disable=0x282000` does not help.
- The reported 7.45.265 regression alone: Debian 7.45.234 is conclusively loaded on both devices and the failure remains.
- World-domain channel restrictions as the immediate explanation: both devices report regulatory domain `00`, but the AP is on channel 1 at 2412 MHz and is visible to the console at full signal.

The Raspberry Pi `brcmfmac_cyw` companion module is present. Attempting to unload it also removes the main `brcmfmac` device, so it was not possible to isolate while retaining the live radio through an ordinary module removal.

## Package-origin side effect

Raspberry Pi's firmware package owned this file:

```text
/usr/lib/modprobe.d/rpi-brcmfmac.conf
options brcmfmac roamoff=1 feature_disable=0x282000
```

Debian's firmware package does not provide it. Both candidate images therefore run normally with `roamoff=0`; `feature_disable` is a supported load-time-only module parameter and is not exposed through sysfs. A runtime test with both Raspberry Pi values restored did not change the failure.

## Relevant reports to evaluate

- [RPi-Distro/firmware-nonfree issue 58](https://github.com/RPi-Distro/firmware-nonfree/issues/58): same local zero-BSSID/status-16 signature with Raspberry Pi firmware 7.45.265; Debian 7.45.234 reportedly fixes it in that environment. Our hardware disproves that fix as sufficient for this Pi-to-Pi case.
- [RPi-Distro/firmware-nonfree issue 38](https://github.com/RPi-Distro/firmware-nonfree/issues/38) and [issue 9](https://github.com/RPi-Distro/firmware-nonfree/issues/9): earlier similar firmware signatures.
- [raspberrypi/linux issue 3619](https://github.com/raspberrypi/linux/issues/3619): brcmfmac AP RSN IE mismatch during the WPA handshake.
- [raspberrypi/linux issue 4976](https://github.com/raspberrypi/linux/issues/4976): potentially related brcmfmac behavior.

Issue 3619 describes a later handshake failure and cannot directly explain the present lack of an authentication frame. It may become relevant after the association problem is fixed. Please check whether its underlying defect is still present in the exact kernel/firmware/NetworkManager combination above rather than assuming an older report still applies.

## Questions for parallel research

1. What brcmfmac or Raspberry Pi kernel change can cause `NL80211_CMD_CONNECT` to complete locally with status 16 before an authentication frame is emitted, specifically with firmware 7.45.234?
2. Are there known BCM43455 incompatibilities when one brcmfmac device is the station and another is the WPA2-PSK-SHA256/PMF AP, independent of the four-way-handshake RSN IE bug?
3. Does Raspberry Pi kernel `6.18.39+rpt-rpi-v8` add vendor patches, `brcmfmac_cyw` integration, SAE/PMF offload, or connect-offload behavior absent from Debian's kernel that could explain the result?
4. Which kernel/firmware pair is the smallest credible comparison? Prefer exact package versions and primary-source evidence.
5. Is there a driver debug mask or tracepoint set that will reveal why firmware rejects the connect request without requiring a custom kernel? If a custom kernel is necessary, identify the smallest instrumentation point.
6. Can AP-side capture be made reliable on the same Broadcom radio, or is an independent monitor-mode adapter required to prove whether any management frame is transmitted?
7. Does fixing the AP to channel 1 and setting a country code change any driver inputs beyond deployment determinism in this exact case? Explain why it could affect a station that already receives the channel-1 beacon.
8. Once association succeeds, is WPA2-PSK-SHA256 with PMF required currently supported in brcmfmac AP mode, or should a separate handshake experiment anticipate the RSN IE mismatch?

## Constraints on proposed fixes

- Preserve NetworkManager as the sole network owner.
- Preserve WPA2-RSN, CCMP, required PMF, mTLS, firewalling, and disabled forwarding unless evidence demonstrates that a specific security setting is incompatible.
- Avoid introducing `hostapd`, a parallel networking path, or a broad kernel pin without direct evidence.
- Prefer one-variable physical experiments whose resulting stage of failure is observable.
- Clearly separate a diagnostic workaround from a production recommendation.

## Requested response format

Please return:

1. The most likely remaining mechanism, with confidence and primary sources.
2. Any contradictions between the sources and this physical evidence.
3. A ranked list of at most three experiments, each naming the single changed variable and the expected distinguishing observation.
4. The smallest defensible next candidate change, if the evidence supports one.
