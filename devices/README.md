# Devices

The old button-pad CAN firmware has been removed. Slice 03 will add an independent ESP32 button-pad project here.

The Servotronic controller is the remaining fan-bench CAN-to-PWM prototype. It has bounded PWM and local failsafes, but no current feedback and is not suitable for a steering-rack solenoid or a car.

The approved replacement firmware for both roles targets the WeAct CAN485 ESP32 device board described in docs/weact-can485-esp32.md. The Servotronic prototype remains only until its independent-device cutover.
