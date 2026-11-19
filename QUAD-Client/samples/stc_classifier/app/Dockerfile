# stc_classifier Dockerfile
#
# Minimal OCI image: just the binary, no rootfs. The host gateway's
# /lib, /usr/lib, /etc, /sys, /dev are bind-mounted in by oci_config.json
# at runc start. This pattern mirrors the production gwapps reference
# apps (see samples/gwapps_fault_detection/upstream/faultdetection/fd/Dockerfile).

FROM scratch

COPY ./build/stc_classifier /app/stc_classifier

CMD ["/app/stc_classifier"]
