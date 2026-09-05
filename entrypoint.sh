#!/bin/sh
# Container entrypoint: set VNC password from env, start KasmVNC on :1.
set -e

VNC_USER="${VNC_USER:-runner}"
VNC_PASS="${VNC_PASS:-123456}"

echo "$VNC_PASS
$VNC_PASS" | kasmvncpasswd -u "$VNC_USER" -o -w

exec vncserver :1 -select-de xfce -fg -websocketPort 8443 \
  -cert /home/runner/.vnc/self.crt -key /home/runner/.vnc/self.key
