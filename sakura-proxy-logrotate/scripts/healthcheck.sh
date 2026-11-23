#!/bin/sh
set -eu
pidof crond >/dev/null 2>&1 || exit 1
test -r /etc/crontabs/root || exit 1
command -v logrotate >/dev/null 2>&1 || exit 1
last="$(cat /var/lib/logrotate/last-success 2>/dev/null)" || exit 1
case "$last" in *[!0-9]*|'') exit 1 ;; esac
now="$(date +%s)" || exit 1
age=$((now - last))
# Cron runs every 15 minutes; 40 minutes of tolerance for VM pauses.
test "$age" -ge 0 && test "$age" -le 2400
