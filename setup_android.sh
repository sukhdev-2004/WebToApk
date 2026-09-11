#!/bin/bash

set -e

echo "Installing Java..."
apt-get update
apt-get install -y openjdk-17-jdk wget unzip

echo "Installing Android SDK..."

export ANDROID_SDK_ROOT=/opt/android-sdk
export ANDROID_HOME=/opt/android-sdk

mkdir -p $ANDROID_SDK_ROOT/cmdline-tools

cd /tmp

wget -q https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip

unzip -q commandlinetools-linux-13114758_latest.zip

mkdir -p $ANDROID_SDK_ROOT/cmdline-tools/latest

mv cmdline-tools/* $ANDROID_SDK_ROOT/cmdline-tools/latest/

export PATH=$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$PATH

yes | sdkmanager --licenses > /dev/null || true

sdkmanager "platform-tools" \
           "platforms;android-36" \
           "build-tools;37.0.0"

echo "Android SDK installation complete."

java -version
sdkmanager --version