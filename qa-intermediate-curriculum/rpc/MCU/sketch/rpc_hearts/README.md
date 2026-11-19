# rpc_hearts

This example demonstrates MCU ↔ Linux RPC communication on the Arduino Uno Q, with a simple LED matrix heart animation triggered from Python.

## Overview

- The MCU exposes an RPC function: `flash_heart`
- The Linux side (Python) calls this function
- When triggered, the LED matrix plays a heart animation

## Directory Structure
```bash
rpc_hearts/
  rpc_hearts.ino        # Main Arduino sketch (must match folder name)
  heart_frames.h        # Animation frames
  README.md
```

## Requirements

- arduino-cli installed
- Arduino Uno Q connected
- Python environment set up for the Linux-side script

## Build and Upload

From inside the rpc_hearts directory:
```bash
arduino-cli compile --fqbn arduino:zephyr:unoq .
arduino-cli upload --fqbn arduino:zephyr:unoq .
```

## Run Python Side

From the parent directory:
```bash
cd ../../MPU/ && python unoq_rpc_heart.py
```
This script will call the `flash_heart` RPC function on the MCU, triggering the animation.

## Notes

- The sketch name must match the directory name (rpc_hearts.ino in rpc_hearts/)
- Only one .ino file with setup() and loop() should exist per sketch folder
- The animation is defined using:
  - HeartStatic → single frame
  - HeartAnim → sequence (used with loadSequence())

## Troubleshooting

Compilation error: "main file missing"
- Ensure the .ino file matches the folder name

Multiple definition errors
- Ensure there is only one .ino file in the directory

Animation not showing
- Verify:
  - matrix.loadSequence(HeartAnim)
  - matrix.playSequence()
