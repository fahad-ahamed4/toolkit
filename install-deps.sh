#!/usr/bin/env bash
set -euo pipefail

if command -v 7zz >/dev/null 2>&1 || command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1; then
  echo "7-Zip CLI already installed."
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo "Please install p7zip-full with root privileges."; exit 1; }
    SUDO="sudo"
  fi
  $SUDO apt-get update
  $SUDO apt-get install -y p7zip-full
elif command -v dnf >/dev/null 2>&1; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo "Please install p7zip and p7zip-plugins with root privileges."; exit 1; }
    SUDO="sudo"
  fi
  $SUDO dnf install -y p7zip p7zip-plugins
elif command -v apk >/dev/null 2>&1; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo "Please install p7zip with root privileges."; exit 1; }
    SUDO="sudo"
  fi
  $SUDO apk add p7zip
elif command -v pacman >/dev/null 2>&1; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo "Please install 7zip with root privileges."; exit 1; }
    SUDO="sudo"
  fi
  $SUDO pacman -Sy --needed 7zip
else
  echo "Unsupported package manager. Install a 7-Zip CLI (7zz, 7z, or 7za) manually."
  exit 1
fi

if ! command -v 7zz >/dev/null 2>&1 && ! command -v 7z >/dev/null 2>&1 && ! command -v 7za >/dev/null 2>&1; then
  echo "Package installed, but no 7-Zip CLI was found. Check your distribution's package name."
  exit 1
fi
echo "Dependencies ready."
