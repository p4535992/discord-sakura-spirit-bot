#!/bin/sh
set -eu
# An immediate first run makes the healthcheck reliable at startup.
/opt/scripts/rotate_once.sh
exec crond -f -l 6 -L /var/log/proxy-logrotate/crond.log
