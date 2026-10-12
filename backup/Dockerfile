FROM postgres:16-alpine

COPY backup.sh /usr/local/bin/backup.sh
COPY crontab /etc/crontabs/root

RUN chmod 700 /usr/local/bin/backup.sh

CMD ["busybox", "crond", "-f", "-d", "8", "-c", "/etc/crontabs"]
