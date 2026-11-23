#!/bin/sh
set -eu
STATE_DIR=/var/lib/logrotate
STATUS_FILE="$STATE_DIR/last-success"
TMP_FILE="$STATE_DIR/.last-success.$$"
LOG=/var/log/proxy-logrotate/rotate.log
mkdir -p "$STATE_DIR" /var/log/proxy-logrotate
trap 'rm -f "$TMP_FILE"' EXIT HUP INT TERM
if /usr/sbin/logrotate -s "$STATE_DIR/status" /etc/logrotate.d/sakura-bot >>"$LOG" 2>&1; then
    date +%s > "$TMP_FILE"
    chmod 600 "$TMP_FILE"
    mv -f "$TMP_FILE" "$STATUS_FILE"
else
    printf '%s: logrotate failed, check configuration and permissions\n' "$(date -Iseconds)" >> "$LOG"
    exit 1
fi
