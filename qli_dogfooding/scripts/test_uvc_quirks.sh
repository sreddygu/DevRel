#!/bin/sh

set -u

restore_driver() {
    unbind_uvc_interfaces
    modprobe -r uvcvideo 2>/dev/null || true
    modprobe uvcvideo nodrop=1 timeout=5000 2>/dev/null || true
}

unbind_uvc_interfaces() {
    for interface in /sys/bus/usb/drivers/uvcvideo/*:*; do
        [ -e "$interface" ] || continue
        basename "$interface" > /sys/bus/usb/drivers/uvcvideo/unbind
    done
    sleep 1
}

find_capture_node() {
    for node in /dev/video*; do
        [ -e "$node" ] || continue
        if v4l2-ctl -d "$node" --list-formats 2>/dev/null | grep -q "MJPG"; then
            printf '%s\n' "$node"
            return 0
        fi
    done
    return 1
}

trap restore_driver EXIT INT TERM

echo "UVC quirk recovery test"
date -Iseconds
uname -a
echo "USB topology:"
lsusb -t 2>/dev/null || true

for quirks in 0 128 2 256 130 384 386; do
    echo
    echo "=== quirks=$quirks ==="
    unbind_uvc_interfaces
    modprobe -r uvcvideo 2>&1 || {
        echo "Unable to unload uvcvideo"
        continue
    }
    modprobe uvcvideo quirks="$quirks" nodrop=1 timeout=5000 2>&1 || {
        echo "Unable to load uvcvideo with quirks=$quirks"
        continue
    }
    sleep 2

    node="$(find_capture_node 2>/dev/null || true)"
    if [ -z "$node" ]; then
        echo "No MJPEG capture node found"
        dmesg | tail -n 20
        continue
    fi

    output="/tmp/uvc_quirks_${quirks}.mjpg"
    rm -f "$output"
    echo "Capture node: $node"
    timeout 12 v4l2-ctl -d "$node" \
        --set-fmt-video=width=320,height=240,pixelformat=MJPG \
        --set-parm=30 \
        --stream-mmap=3 \
        --stream-count=1 \
        --stream-poll \
        --stream-to="$output" 2>&1
    status=$?
    size=0
    [ -f "$output" ] && size="$(wc -c < "$output")"
    echo "Capture status: $status"
    echo "Capture bytes: $size"
    dmesg | tail -n 20
done

echo
echo "=== restoring default driver parameters ==="
restore_driver
printf 'quirks='; cat /sys/module/uvcvideo/parameters/quirks 2>/dev/null || true
printf 'nodrop='; cat /sys/module/uvcvideo/parameters/nodrop 2>/dev/null || true
printf 'timeout='; cat /sys/module/uvcvideo/parameters/timeout 2>/dev/null || true
