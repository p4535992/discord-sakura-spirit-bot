# Minimal sidecar for centralised log rotation; no Docker socket access.
FROM alpine:3.24.4

RUN apk add --no-cache logrotate tzdata \
    && mkdir -p /var/log/traefik /var/log/sakura-bot /var/log/proxy-logrotate /var/lib/logrotate

COPY config/crontab /etc/crontabs/root
COPY config/logrotate.conf /etc/logrotate.d/sakura-bot
COPY scripts/rotate_once.sh /opt/scripts/rotate_once.sh
COPY scripts/healthcheck.sh /opt/scripts/healthcheck.sh
COPY scripts/start.sh /opt/scripts/start.sh

RUN chmod 0600 /etc/crontabs/root \
    && chmod 0644 /etc/logrotate.d/sakura-bot \
    && chmod 0755 /opt/scripts/rotate_once.sh /opt/scripts/healthcheck.sh /opt/scripts/start.sh

CMD ["/bin/sh", "/opt/scripts/start.sh"]
