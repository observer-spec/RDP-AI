# Prebaked cloud desktop image for RDP-AI.
# XFCE4 + Google Chrome + KasmVNC — installed once, pulled in seconds on every run.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    xfce4 xfce4-terminal xfce4-goodies dbus-x11 scrot openssl wget curl ca-certificates \
    libu2f-udev libvulkan1 python3 python3-pip supervisor tini \
    && rm -rf /var/lib/apt/lists/*

# --- Google Chrome ---
ADD https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb /tmp/chrome.deb
RUN apt-get install -y /tmp/chrome.deb && rm /tmp/chrome.deb

# Chrome wrapper: container-safe flags, GPU enabled via SwiftShader (no --disable-gpu)
RUN printf '#!/bin/sh\nexec /usr/bin/google-chrome-stable --no-sandbox --disable-dev-shm-usage \\\n  --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \\\n  --password-store=basic --no-first-run "$@"\n' > /usr/local/bin/google-chrome-runner \
    && chmod +x /usr/local/bin/google-chrome-runner

# Register as default browser
RUN update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/local/bin/google-chrome-runner 300 \
    && update-alternatives --set x-www-browser /usr/local/bin/google-chrome-runner \
    && update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/local/bin/google-chrome-runner 300 \
    && update-alternatives --set gnome-www-browser /usr/local/bin/google-chrome-runner

# --- KasmVNC ---
ADD https://github.com/kasmtech/KasmVNC/releases/download/v1.5.0/kasmvncserver_noble_1.5.0_amd64.deb /tmp/kasmvnc.deb
RUN apt-get install -y /tmp/kasmvnc.deb && rm /tmp/kasmvnc.deb

# --- Non-root desktop user ---
RUN userdel -r ubuntu 2>/dev/null; useradd -m -s /bin/bash runner && echo "runner:changeme" | chpasswd

USER runner
WORKDIR /home/runner

# VNC config baked at build time; password set at runtime from secrets
RUN mkdir -p ~/.vnc ~/Desktop && touch ~/.Xauthority \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
       -keyout ~/.vnc/self.key -out ~/.vnc/self.crt \
       -subj "/C=US/ST=State/L=City/O=Org/CN=kasmvnc" \
    && chmod 600 ~/.vnc/self.key \
    && printf '#!/bin/sh\nunset SESSION_MANAGER\nunset DBUS_SESSION_BUS_ADDRESS\ndbus-launch --exit-with-session startxfce4 &\n' > ~/.vnc/xstartup \
    && chmod +x ~/.vnc/xstartup \
    && printf 'network:\n  ssl:\n    require_ssl: false\n    pem_certificate: /home/runner/.vnc/self.crt\n    pem_key: /home/runner/.vnc/self.key\ndesktop:\n  resolution:\n    width: 1920\n    height: 1080\n  allow_resize: true\n' > ~/.vnc/kasmvnc.yaml \
    && printf '[Desktop Entry]\nVersion=1.0\nType=Application\nName=Google Chrome\nExec=/usr/local/bin/google-chrome-runner %%U\nIcon=google-chrome\nTerminal=false\nCategories=Network;WebBrowser;\n' > ~/Desktop/Google-Chrome.desktop \
    && chmod +x ~/Desktop/Google-Chrome.desktop

COPY entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh
USER runner

EXPOSE 8443
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
