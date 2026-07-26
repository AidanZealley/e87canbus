import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

ARDUINO_STUB = "#pragma once\n#include <stdint.h>\ntypedef unsigned char byte;\n"


def build_and_run(tmp_path: Path, source: Path, name: str) -> None:
    """Compile one firmware header against a stub Arduino and run its assertions."""

    executable = tmp_path / name
    compiler = os.environ.get("CXX", "c++")
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        pytest.skip(f"host C++ compiler {compiler!r} is unavailable")
    probe = subprocess.run(
        [compiler_path, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip(f"host C++ compiler {compiler!r} cannot execute: {probe.stderr.strip()}")
    command = [
        compiler_path,
        "-std=gnu++11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(tmp_path),
        "-I",
        str(ROOT / "devices" / "button-pad" / "include"),
        str(source),
        "-o",
        str(executable),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True)


def test_button_pad_protocol_state_machine_host_side(tmp_path: Path) -> None:
    (tmp_path / "Arduino.h").write_text(ARDUINO_STUB, encoding="utf-8")
    source = tmp_path / "protocol_state_test.cpp"
    source.write_text(
        r"""
#include <cassert>
#include <cstdint>
#include "protocol_state.h"

using namespace button_pad;

int main() {
    SequenceState sequences;
    assert(sequences.nextHello() == 0);
    for (int i = 0; i < 200; ++i) {
        sequences.nextHeartbeat();
    }
    assert(sequences.nextHello() == 1);
    assert(sequences.nextHeartbeat() == 200);

    sequences.hello = 255;
    assert(sequences.nextHello() == 255);
    assert(sequences.nextHello() == 0);

    uint8_t hello[BUTTON_PAD_HELLO_LENGTH] = {};
    encodeHello(hello, 1, 1, 0x1234, 0x56);
    const uint8_t expectedHello[] = {0x01, 0x01, 0x00, 0x34, 0x12, 0x56, 0x00, 0x00};
    for (uint8_t index = 0; index < BUTTON_PAD_HELLO_LENGTH; ++index) {
        assert(hello[index] == expectedHello[index]);
    }

    uint8_t heartbeat[BUTTON_PAD_HEARTBEAT_LENGTH] = {};
    encodeHeartbeat(heartbeat, 1, 0x1234, 0xABCD, 0x57, STATUS_OK);
    const uint8_t expectedHeartbeat[] = {0x01, 0x00, 0x34, 0x12, 0xCD, 0xAB, 0x57, 0x00};
    for (uint8_t index = 0; index < BUTTON_PAD_HEARTBEAT_LENGTH; ++index) {
        assert(heartbeat[index] == expectedHeartbeat[index]);
    }

    DeviceStatus transient{DeviceState::OPERATIONAL, STATUS_OK};
    transient = heartbeatSendCompleted(transient, false);
    assert(transient.state == DeviceState::LOCAL_FAULT);
    assert(transient.code == STATUS_CAN_SEND_FAILED);
    transient = heartbeatSendCompleted(transient, true);
    assert(transient.state == DeviceState::OPERATIONAL);
    assert(transient.code == STATUS_OK);

    const DeviceStatus bootFault{DeviceState::LOCAL_FAULT, STATUS_LOCAL_FAULT};
    assert(heartbeatSendCompleted(bootFault, true).code == STATUS_LOCAL_FAULT);
    assert(!shouldBeginDiscovery(DeviceState::LOCAL_FAULT, false, false));
    assert(shouldBeginDiscovery(DeviceState::LOCAL_FAULT, true, false));
    assert(!shouldBeginDiscovery(DeviceState::OPERATIONAL, true, true));
}
""",
        encoding="utf-8",
    )
    build_and_run(tmp_path, source, "protocol_state_test")


def test_button_pad_effect_frame_dispatch_host_side(tmp_path: Path) -> None:
    """The 0x701 guard and pulse dispatch, exercised without the Arduino runtime.

    ``main.cpp`` cannot be compiled on the host, so the decision it makes about an
    effect frame lives in ``button_pad_effect.h`` and is pinned here. The simulated
    pad in ``runners/simulation/devices/neotrellis.py`` mirrors these same cases.
    """

    (tmp_path / "Arduino.h").write_text(ARDUINO_STUB, encoding="utf-8")
    source = tmp_path / "button_pad_effect_test.cpp"
    source.write_text(
        r"""
#include <cassert>
#include <cstdint>
#include "button_pad_effect.h"

using namespace button_pad;

namespace {

const uint8_t PAD_BUTTONS = 16;

EffectCommand decode(uint8_t version, uint8_t opcode, uint8_t index, uint8_t pulses) {
    const uint8_t payload[BUTTON_PAD_EFFECT_LENGTH] = {
        version, opcode, index, 0x5A, pulses, 0x2A, 0x8C, 0x13};
    return decodeEffectCommand(payload, BUTTON_PAD_EFFECT_LENGTH, PAD_BUTTONS);
}

}  // namespace

int main() {
    // A one-pulse frame carries an arbitrary colour through to the single-blink
    // entry point, verbatim.
    const EffectCommand single = decode(BUTTON_PAD_EFFECT_COMMAND_VERSION,
                                        BUTTON_PAD_EFFECT_BLINK, 3, 1);
    assert(single.action == EffectAction::SINGLE_BLINK);
    assert(single.buttonIndex == 3);
    assert(single.red == 0x2A && single.green == 0x8C && single.blue == 0x13);

    const EffectCommand doubled = decode(BUTTON_PAD_EFFECT_COMMAND_VERSION,
                                         BUTTON_PAD_EFFECT_BLINK, 15, 2);
    assert(doubled.action == EffectAction::DOUBLE_BLINK);
    assert(doubled.buttonIndex == 15);
    assert(doubled.red == 0x2A && doubled.green == 0x8C && doubled.blue == 0x13);

    // A pulse count outside 1-2 has no firmware entry point.
    assert(decode(BUTTON_PAD_EFFECT_COMMAND_VERSION, BUTTON_PAD_EFFECT_BLINK, 3, 0).action ==
           EffectAction::IGNORE);
    assert(decode(BUTTON_PAD_EFFECT_COMMAND_VERSION, BUTTON_PAD_EFFECT_BLINK, 3, 3).action ==
           EffectAction::IGNORE);

    // Version 1 gave bytes 4-7 a different meaning, so it must not be read as a
    // black one-pulse blink. The retired breathe opcode 0x02 is equally unknown.
    assert(decode(1, BUTTON_PAD_EFFECT_BLINK, 3, 1).action == EffectAction::IGNORE);
    assert(decode(BUTTON_PAD_EFFECT_COMMAND_VERSION, 0x02, 3, 1).action == EffectAction::IGNORE);

    // A button outside the pad, and a frame that is not DLC-8.
    assert(decode(BUTTON_PAD_EFFECT_COMMAND_VERSION, BUTTON_PAD_EFFECT_BLINK, PAD_BUTTONS, 1)
               .action == EffectAction::IGNORE);
    const uint8_t truncated[4] = {BUTTON_PAD_EFFECT_COMMAND_VERSION, BUTTON_PAD_EFFECT_BLINK, 3, 1};
    assert(decodeEffectCommand(truncated, 4, PAD_BUTTONS).action == EffectAction::IGNORE);
}
""",
        encoding="utf-8",
    )
    build_and_run(tmp_path, source, "button_pad_effect_test")
