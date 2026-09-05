#!/bin/sh
# Container entrypoint (runs as ROOT): VNC password, RDP via xrdp attached to
# the local KasmVNC display (:1), then the KasmVNC web desktop.
# RDP (mstsc -> :3389) and browser (:8443) share the same screen.
set -e

VNC_USER="${VNC_USER:-runner}"
VNC_PASS="${VNC_PASS:-123456}"
USER_HOME=$(eval echo "~$VNC_USER")

# KasmVNC password file (must be written as the desktop user)
su -s /bin/sh "$VNC_USER" -c \
  'printf "%s\n%s\n" "$VNC_PASS" "$VNC_PASS" | kasmvncpasswd -u "$VNC_USER" -o -w'

# Same credentials for RDP (NLA authenticates against the system account)
printf '%s:%s\n' "$VNC_USER" "$VNC_PASS" | chpasswd

# RDP server (direct-VNC mode: no sesman needed)
mkdir -p /var/run/xrdp
if ! /usr/sbin/xrdp; then
  echo "WARN: xrdp failed to start — RDP on :3389 unavailable (web desktop unaffected)"
fi

exec su -s /bin/sh "$VNC_USER" -c \
  "exec vncserver :1 -select-de xfce -fg -websocketPort 8443 -cert $USER_HOME/.vnc/self.crt -key $USER_HOME/.vnc/self.key"
