import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_button_pad_protocol_state_machine_host_side(tmp_path: Path) -> None:
    (tmp_path / "Arduino.h").write_text(
        "#pragma once\n#include <stdint.h>\ntypedef unsigned char byte;\n",
        encoding="utf-8",
    )
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
    executable = tmp_path / "protocol_state_test"
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
