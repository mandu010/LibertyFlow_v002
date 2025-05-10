#!/bin/bash

# Update system
sudo apt update

# Install Chrome dependencies
sudo apt install -y wget unzip xvfb libxi6 libgconf-2-4 default-jdk

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Check Chrome version
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1)
echo "Chrome version: $CHROME_VERSION"

# Install chromedriver that matches Chrome version
wget -N "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION"
CHROMEDRIVER_VERSION=$(cat "LATEST_RELEASE_$CHROME_VERSION")
echo "Installing chromedriver version: $CHROMEDRIVER_VERSION"
wget -N "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
unzip -o chromedriver_linux64.zip
chmod +x chromedriver
sudo mv chromedriver /usr/local/bin/
rm chromedriver_linux64.zip "LATEST_RELEASE_$CHROME_VERSION"

# Verify installations
echo "Chrome version: $(google-chrome --version)"
echo "Chromedriver version: $(chromedriver --version)"

# Install Xvfb for virtual display
sudo apt install -y xvfb

# Install Python dependencies
pip install selenium pyotp pyvirtualdisplay
