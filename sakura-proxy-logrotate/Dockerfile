# Minimal sidecar for centralised log rotation; no Docker socket access.
FROM alpine:3.24.4

# The bot log volume is shared with the bot container: create it with the bot
# UID (10001) so the volume keeps the right owner whichever container seeds it.
RUN apk add --no-cache logrotate tzdata \
    && mkdir -p /var/log/traefik /var/log/sakura-bot /var/log/sakura-proxy-logrotate /var/lib/logrotate \
    && chown 10001:10001 /var/log/sakura-bot

COPY config/crontab /etc/crontabs/root
COPY config/logrotate.conf /etc/logrotate.d/sakura-bot
COPY scripts/rotate_once.sh /opt/scripts/rotate_once.sh
COPY scripts/healthcheck.sh /opt/scripts/healthcheck.sh
COPY scripts/start.sh /opt/scripts/start.sh

RUN chmod 0600 /etc/crontabs/root \
    && chmod 0644 /etc/logrotate.d/sakura-bot \
    && chmod 0755 /opt/scripts/rotate_once.sh /opt/scripts/healthcheck.sh /opt/scripts/start.sh

CMD ["/bin/sh", "/opt/scripts/start.sh"]
