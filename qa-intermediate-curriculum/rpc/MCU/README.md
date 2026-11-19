# MCU RPC Firmware (Arduino Uno Q)

This directory contains the MCU-side firmware for enabling RPC
communication with the Linux MPU on the Arduino Uno Q.

------------------------------------------------------------------------

## Requirements

### Arduino CLI

Check if installed:

``` bash
arduino-cli --version
```

Install if needed:

``` bash
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
sudo mv bin/arduino-cli /usr/local/bin/
```

------------------------------------------------------------------------

### Required Libraries

``` bash
arduino-cli lib update-index
arduino-cli lib install Arduino_RouterBridge
arduino-cli lib install Arduino_RPC
```

------------------------------------------------------------------------

## Build & Flash

### Compile

``` bash
arduino-cli compile --fqbn arduino:zephyr:unoq .
```

### Upload (Network-based)

``` bash
arduino-cli upload \
  -p <network_port> \
  --fqbn arduino:zephyr:unoq .
```

------------------------------------------------------------------------

## Notes

-   Folder name must match `.ino` file name

-   Stop router if upload fails:

    ``` bash
    sudo systemctl stop arduino-router
    ```

-   Restart after:

    ``` bash
    sudo systemctl start arduino-router
    ```

------------------------------------------------------------------------

## What This Does

-   Responds to RPC calls from Linux
-   Enables bidirectional communication

------------------------------------------------------------------------
