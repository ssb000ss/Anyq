#!/bin/sh
# Custom entrypoint: copy settings template into the config volume,
# inject SEARXNG_SECRET_KEY, then hand off to the original SearXNG entrypoint.
set -eu

SETTINGS_DEST="${SEARXNG_SETTINGS_PATH:-/etc/searxng/settings.yml}"

mkdir -p "$(dirname "$SETTINGS_DEST")"

# Always copy from the baked-in template so restarts pick up image changes.
cp /searxng-settings-template.yml "$SETTINGS_DEST"

if [ -n "${SEARXNG_SECRET_KEY:-}" ]; then
    sed -i "s/__SEARXNG_SECRET_KEY__/${SEARXNG_SECRET_KEY}/g" "$SETTINGS_DEST"
else
    echo "WARNING: SEARXNG_SECRET_KEY is not set — using random key"
    RANDOM_KEY=$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')
    sed -i "s/__SEARXNG_SECRET_KEY__/${RANDOM_KEY}/g" "$SETTINGS_DEST"
fi

exec /usr/local/searxng/entrypoint.sh "$@"
