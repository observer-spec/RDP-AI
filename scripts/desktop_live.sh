#!/bin/sh
# Live fallback: install XFCE + Chrome + KasmVNC on the runner itself.
set -e
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  xfce4 xfce4-terminal xfce4-goodies dbus-x11 scrot openssl wget curl libu2f-udev libvulkan1

wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

sudo tee /usr/local/bin/google-chrome-runner << 'EOF' > /dev/null
#!/bin/sh
exec /usr/bin/google-chrome-stable --no-sandbox --disable-dev-shm-usage \
  --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
  --password-store=basic --no-first-run "$@"
EOF
sudo chmod +x /usr/local/bin/google-chrome-runner

mkdir -p /home/runner/Desktop /home/runner/.config/xfce4
cat << 'EOF' > /home/runner/Desktop/Google-Chrome.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Google Chrome
Comment=Access the Internet
Exec=/usr/local/bin/google-chrome-runner %U
Icon=google-chrome
Path=/home/runner
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
EOF
chmod +x /home/runner/Desktop/Google-Chrome.desktop

sudo update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/local/bin/google-chrome-runner 300
sudo update-alternatives --set x-www-browser /usr/local/bin/google-chrome-runner
sudo update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/local/bin/google-chrome-runner 300
sudo update-alternatives --set gnome-www-browser /usr/local/bin/google-chrome-runner

# KasmVNC
wget -q https://github.com/kasmtech/KasmVNC/releases/download/v1.5.0/kasmvncserver_noble_1.5.0_amd64.deb
sudo apt-get install -y ./kasmvncserver_noble_1.5.0_amd64.deb
rm kasmvncserver_noble_1.5.0_amd64.deb

mkdir -p ~/.vnc
touch ~/.Xauthority
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /home/runner/.vnc/self.key -out /home/runner/.vnc/self.crt \
  -subj "/C=US/ST=State/L=City/O=Org/CN=kasmvnc"
chmod 600 /home/runner/.vnc/self.key

cat << 'EOF' > ~/.vnc/xstartup
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
dbus-launch --exit-with-session startxfce4 &
EOF
chmod +x ~/.vnc/xstartup

printf '%s\n%s\n' "$VNC_PASS" "$VNC_PASS" | kasmvncpasswd -u "$VNC_USER" -o -w

cat << 'EOF' > ~/.vnc/kasmvnc.yaml
network:
  ssl:
    require_ssl: false
    pem_certificate: /home/runner/.vnc/self.crt
    pem_key: /home/runner/.vnc/self.key
desktop:
  resolution:
    width: 1920
    height: 1080
  allow_resize: true
EOF

vncserver :1 -select-de xfce -websocketPort 8443 -cert /home/runner/.vnc/self.crt -key /home/runner/.vnc/self.key

# RDP via xrdp (attaches to the same :1 screen through local VNC; same login)
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xrdp
sudo cp "${GITHUB_WORKSPACE:-$PWD}/scripts/xrdp.ini" /etc/xrdp/xrdp.ini
printf '%s:%s\n' "$VNC_USER" "$VNC_PASS" | sudo chpasswd
sudo mkdir -p /var/run/xrdp
sudo /usr/sbin/xrdp || echo "::warning::xrdp failed to start (web desktop unaffected)"

echo "DISPLAY=:1" >> "$GITHUB_ENV"
