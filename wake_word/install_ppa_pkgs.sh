#!/bin/bash -e

# Set '-x' only if the option is neither '-h' nor '--help'
if [ $# -ne 1 ] || [ $# -gt 0 -a "$1" != "-h" -a "$1" != "--help" ]; then
	set -x
fi

# Configuration used by the script
XDG_EXPORT="export XDG_RUNTIME_DIR=/run/user/\$(id -u ubuntu)"
VERSION=0.1
[ -d $(dirname $(realpath $0))/.git ] &&
	VERSION+=+$(git -C $(dirname $(realpath $0)) describe --always)

# Common user and home dir for the ubuntu
USER_NAME=ubuntu
USER_HOME=$(eval echo "~$USER_NAME")

# Usage function with colored output
usage() {
	set +x
	printf "\033[1;37mUsage:\033[0m\n"
	printf "  %s [options]\n" "$0"
	printf "\n"
	printf "\033[1;37mDescription:\033[0m\n"
	printf "  Helps you quickly enable IQ9075's peripheral functions (CAM, AI, Audio, etc.)\n"
	printf "\n"
	printf "\033[1;37mOptions:\033[0m\n"
	printf "\033[1;37m  -h, --help\033[0m              Display this help message\n"
}

add_ppa()
{
	sudo apt-get update
}

add_cam_ai_pkgs()
{
	# CAM/AI -- QCOM PPA
	PKG_LIST+=(
		gstreamer1.0-plugins-base-apps
		gstreamer1.0-qcom-python-examples
		gstreamer1.0-qcom-sample-apps
		gstreamer1.0-tools
		libqnn-dev
		libsnpe-dev
		qcom-fastcv-binaries-dev
		qcom-libdmabufheap-dev
		qcom-sensors-test-apps
		qnn-tools
		snpe-tools
		tensorflow-lite-qcom-apps
		gstreamer1.0-plugins-qcom
		gstreamer1.0-libav
		gstreamer1.0-plugins-ugly
	)
}

weston_xwayland_support() {
    if dpkg -l | grep -q '^ii  ubuntu-desktop'; then
        echo "Desktop build detected (ubuntu-desktop)."
		# Desktop-specific packages
		PKG_LIST+=(
			qcom-adreno-cl-dev
		)
        # Desktop-only: Update Mesa
        echo "Updating Mesa for Desktop build..."
        sudo add-apt-repository -y ppa:kisak/kisak-mesa
        sudo apt-get update
        sudo apt-get install --only-upgrade -y libegl-mesa0		
    else
		echo "Server build detected"
		# Server-specific packages
		PKG_LIST+=(
			qcom-adreno1
			weston-autostart
			xwayland
		)
	fi
}

setup_media_and_xdg()
{
    if dpkg -l | grep -q '^ii  ubuntu-desktop'; then
        echo "Desktop build detected (ubuntu-desktop)."
    else
		echo "Server build detected. Add following packages"
		sudo mkdir -p /etc/media
		sudo chown -R ubuntu /etc/media
		grep -qxF "$XDG_EXPORT" $USER_HOME/.bashrc || echo "$XDG_EXPORT" >> $USER_HOME/.bashrc
		sudo bash -c "grep -qxF '${XDG_EXPORT}' /root/.bashrc || echo '${XDG_EXPORT}' >> /root/.bashrc"
	fi
}

add_system_pkgs()
{
	PKG_LIST+=(
		ffmpeg
		net-tools
		pulseaudio-utils
		python3-pip
		selinux-utils
		unzip
		v4l-utils
		yavta
	)
}

install()
{
	sudo apt-get install -y ${PKG_LIST[@]}
	sudo apt-get upgrade -y
}

finalize()
{
	sync; sync; sync
	if [ $reboot -eq 1 ]; then
		echo "Setup completed. System will reboot in 10 seconds..."
		sleep 10
		sudo reboot
	fi
}

# Main execution logic
main() {
	echo "IQ9075 Setup Script"
	echo "  Version $VERSION"
	echo "======================="

	local reboot=1

	# Parse arguments and execute accordingly
	while [ "$#" -gt 0 ]; do
		case "$1" in
			-h|--help)
				usage
				exit 0
				;;
			*)
				echo "Unknown option: $1"
				echo "Use --help for usage information"
				exit 1
				;;
		esac
		shift
	done

	add_ppa
	setup_media_and_xdg
	add_cam_ai_pkgs
	weston_xwayland_support
	add_system_pkgs
	install
	finalize
	echo "Script completed successfully!"
}

# Start the script
main "$@"