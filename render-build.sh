#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python requirements
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir --upgrade -r requirements.txt
python3 -m pip install -U yt-dlp

mkdir -p bin

# Automatically download N_m3u8DL-RE for Linux if not already installed
if ! command -v N_m3u8DL-RE &> /dev/null && [ ! -f "bin/N_m3u8DL-RE" ]; then
    echo "[Render Build] Downloading N_m3u8DL-RE for Linux x64..."
    mkdir -p /tmp/n_m3u8_install
    curl -sL "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.6.0-beta/N_m3u8DL-RE_v0.6.0-beta_linux-x64_20260629.tar.gz" -o /tmp/n_m3u8_install/n_m3u8.tar.gz
    tar -xzf /tmp/n_m3u8_install/n_m3u8.tar.gz -C /tmp/n_m3u8_install/
    mv /tmp/n_m3u8_install/N_m3u8DL-RE bin/N_m3u8DL-RE
    chmod +x bin/N_m3u8DL-RE
    rm -rf /tmp/n_m3u8_install
    echo "[Render Build] N_m3u8DL-RE installed to bin/N_m3u8DL-RE"
fi

# Automatically download Bento4 mp4decrypt for Linux if not already installed
if ! command -v mp4decrypt &> /dev/null && [ ! -f "bin/mp4decrypt" ]; then
    echo "[Render Build] Downloading Bento4 mp4decrypt for Linux x64..."
    mkdir -p /tmp/bento4_install
    curl -sL "https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip" -o /tmp/bento4_install/bento4.zip
    unzip -q /tmp/bento4_install/bento4.zip -d /tmp/bento4_install
    mv /tmp/bento4_install/Bento4-SDK-1-6-0-641.x86_64-unknown-linux/bin/mp4decrypt bin/mp4decrypt
    chmod +x bin/mp4decrypt
    rm -rf /tmp/bento4_install
    echo "[Render Build] Bento4 mp4decrypt installed to bin/mp4decrypt"
fi
