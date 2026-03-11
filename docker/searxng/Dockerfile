FROM searxng/searxng:latest

# Bake settings template into the image.
# The custom entrypoint copies it to /etc/searxng/settings.yml at runtime
# and injects the secret key from SEARXNG_SECRET_KEY env var.
COPY settings.yml /searxng-settings-template.yml
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
