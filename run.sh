#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting GridMate add-on..."

export FLASK_ENV=production
export PYTHONUNBUFFERED=1

bashio::log.info "SUPERVISOR_TOKEN is $([ -n \"$SUPERVISOR_TOKEN\" ] && echo 'set' || echo 'NOT set')"
bashio::log.info "Data directory: /data (exists=$([ -d /data ] && echo 'yes' || echo 'no'))"

exec python3 /app/app.py