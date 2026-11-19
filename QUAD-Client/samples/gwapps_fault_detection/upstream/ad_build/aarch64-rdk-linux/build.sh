#!/bin/bash

set -euo pipefail
set -x

##validate input args to the build script
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <app_or_lib_to_build>"
    exit 1
fi

APP_OR_LIB_TO_BUILD=$1
CURRENT_DIR=$(pwd)
GWAPPS_INSTALL_DIR=${CURRENT_DIR}/../../ad_libs_bins/aarch64-rdk-linux/
GWAPPS_FRAMEWORK_LIBS_BIN_DIR=${CURRENT_DIR}/../../../frmwrk/gwapps_frmwrk_libs_bins/aarch64-rdk-linux/

# Setup toolchain and environment
setup_toolchain() {
        TOOLCHAIN_DIR="${CURRENT_DIR}/../../../toolchain/aarch64-rdk-linux/toolchain/gcc-cross-aarch64/usr/bin/aarch64-rdk-linux"
        export PATH=${TOOLCHAIN_DIR}:$PATH
        SYSROOT="${TOOLCHAIN_DIR}/../../../../recipe-sysroot"
        export CC="$TOOLCHAIN_DIR/aarch64-rdk-linux-gcc"
        export CXX="$TOOLCHAIN_DIR/aarch64-rdk-linux-g++"
        export CFLAGS="--sysroot=$SYSROOT -I$SYSROOT/usr/include"
        export CXXFLAGS="--sysroot=$SYSROOT -I$SYSROOT/usr/include"
        export LDFLAGS="--sysroot=$SYSROOT -L$SYSROOT/usr/lib"
}

build_ad_lib() {
	echo "Removing ad lib..."
	rm -rf "$GWAPPS_INSTALL_DIR"/libad_lib.so
	setup_toolchain
	echo "Building ad_lib..."

	cd ${CURRENT_DIR}/../../faultdetection/fd_lib/ || exit 1
	rm -rf build
	mkdir -p build && cd build

	cmake .. \
	-DCMAKE_C_COMPILER="$CC" \
	-DCMAKE_CXX_COMPILER="$CXX" \
	-DGWAPPS_INSTALL_DIR="$GWAPPS_INSTALL_DIR" \
	-DGWAPPS_FRAMEWORK_LIBS_BIN_DIR="$GWAPPS_FRAMEWORK_LIBS_BIN_DIR" \
	-DCMAKE_SYSROOT="$SYSROOT"

	make -j$(nproc) 
	cd ${CURRENT_DIR}
}

build_ad_app() {
	echo "Removing ad app..."
	rm -rf "$GWAPPS_INSTALL_DIR"/ad
	setup_toolchain
	echo "Building ad app..."

	cd ${CURRENT_DIR}/../../faultdetection/fd/ || exit 1
	rm -rf build
	mkdir -p build && cd build

	cmake .. \
	-DCMAKE_C_COMPILER="$CC" \
	-DCMAKE_CXX_COMPILER="$CXX" \
	-DGWAPPS_INSTALL_DIR="$GWAPPS_INSTALL_DIR" \
	-DGWAPPS_FRAMEWORK_LIBS_BIN_DIR="$GWAPPS_FRAMEWORK_LIBS_BIN_DIR" \
	-DCMAKE_SYSROOT="$SYSROOT"

	make  -j$(nproc)
	cd ${CURRENT_DIR}
}

# Fetch OpenWrt's ipkg-build packaging script on demand. It is third-party
# (OpenWrt, GPL) so it is NOT committed to this repo — see .gitignore and
# samples/gwapps_fault_detection/README.md. Override the source with
# IPKG_BUILD_URL if your network blocks the default.
ensure_ipkg_build() {
	if [ -x "${CURRENT_DIR}/ipkg-build" ]; then
		return 0
	fi
	IPKG_BUILD_URL="${IPKG_BUILD_URL:-https://git.openwrt.org/?p=project/opkg.git;a=blob_plain;f=utils/ipkg-build;hb=HEAD}"
	echo "Fetching ipkg-build from ${IPKG_BUILD_URL} ..."
	if command -v curl >/dev/null 2>&1; then
		curl -fsSL "$IPKG_BUILD_URL" -o "${CURRENT_DIR}/ipkg-build"
	elif command -v wget >/dev/null 2>&1; then
		wget -qO "${CURRENT_DIR}/ipkg-build" "$IPKG_BUILD_URL"
	else
		echo "ERROR: need curl or wget to fetch ipkg-build (or drop it in ${CURRENT_DIR}/ manually)." >&2
		exit 1
	fi
	chmod +x "${CURRENT_DIR}/ipkg-build"
}

generate_ipk() {
	echo "Removing existing ipk..."
	ensure_ipkg_build
	rm -rf "$GWAPPS_INSTALL_DIR"/*.ipk
	cp "$GWAPPS_INSTALL_DIR"/ad "$GWAPPS_INSTALL_DIR"/mylib_package/usr/bin/
	cp "$GWAPPS_INSTALL_DIR"/libad_lib.so "$GWAPPS_INSTALL_DIR"/mylib_package/usr/lib/libad_lib.so
	cp "$SYSROOT"/usr/lib/libqca_nl80211_wrapper.so "$GWAPPS_INSTALL_DIR"/mylib_package/usr/lib/libqca_nl80211_wrapper.so
	./ipkg-build  "$GWAPPS_INSTALL_DIR"/mylib_package/ "$GWAPPS_INSTALL_DIR"
}

generate_docker_and_runc_ipk() {
    ensure_ipkg_build
    mkdir -p "$GWAPPS_INSTALL_DIR"/docker/CONTROL
    mkdir -p "$GWAPPS_INSTALL_DIR"/docker/tmp

    mkdir -p "$GWAPPS_INSTALL_DIR"/runc/CONTROL
    mkdir -p "$GWAPPS_INSTALL_DIR"/runc/tmp

    # Modify control file for docker - replace AD_ with AD-docker_
    sed -e 's/^Package: AD_/Package: AD-docker_/' \
        -e 's/^Description:.*$/Description: Anomaly Detection package for Docker/' \
        "$GWAPPS_INSTALL_DIR"/mylib_package/CONTROL/control \
        > "$GWAPPS_INSTALL_DIR"/docker/CONTROL/control

    # Modify control file for runc - replace AD_ with AD-runc_
    sed -e 's/^Package: AD_/Package: AD-runc_/' \
        -e 's/^Description:.*$/Description: Anomaly Detection package for Runc/' \
        "$GWAPPS_INSTALL_DIR"/mylib_package/CONTROL/control \
        > "$GWAPPS_INSTALL_DIR"/runc/CONTROL/control

    cp "$GWAPPS_INSTALL_DIR"/ad-docker-image.tar "$GWAPPS_INSTALL_DIR"/docker/tmp
    cp "$GWAPPS_INSTALL_DIR"/ad-runc.tar.gz "$GWAPPS_INSTALL_DIR"/runc/tmp
    cp -r "$GWAPPS_INSTALL_DIR"/mylib_package/etc "$GWAPPS_INSTALL_DIR"/docker/
    cp -r "$GWAPPS_INSTALL_DIR"/mylib_package/usr "$GWAPPS_INSTALL_DIR"/docker/
    cp -r "$GWAPPS_INSTALL_DIR"/mylib_package/etc "$GWAPPS_INSTALL_DIR"/runc/
    cp -r "$GWAPPS_INSTALL_DIR"/mylib_package/usr "$GWAPPS_INSTALL_DIR"/runc/

    ./ipkg-build "$GWAPPS_INSTALL_DIR"/docker/ "$GWAPPS_INSTALL_DIR"
    ./ipkg-build "$GWAPPS_INSTALL_DIR"/runc/ "$GWAPPS_INSTALL_DIR"
}

build_all() {
	build_ad_lib
	build_ad_app
	generate_ipk
#	generate_docker_and_runc_ipk
}

case $APP_OR_LIB_TO_BUILD in
    "ad_lib")
        build_ad_lib
        ;;
    "ad_app")
        build_ad_app
        ;;
    "all")
        build_all
        ;;
    *)
        echo "Unknown app: $APP_OR_LIB_TO_BUILD"
        exit 1
        ;;
esac
