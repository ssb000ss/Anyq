FROM alpine:3.19

RUN apk add --no-cache tor curl

# Minimal torrc: SOCKS5 on 0.0.0.0:9050, no control port
RUN echo "SocksPort 0.0.0.0:9050" > /etc/tor/torrc && \
    echo "SocksPolicy accept *" >> /etc/tor/torrc && \
    echo "Log notice stderr" >> /etc/tor/torrc && \
    echo "DataDirectory /var/lib/tor" >> /etc/tor/torrc && \
    mkdir -p /var/lib/tor && \
    chown -R tor:tor /var/lib/tor && \
    chmod 700 /var/lib/tor

EXPOSE 9050

USER tor

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -s --socks5-hostname localhost:9050 --max-time 10 https://check.torproject.org/api/ip \
    | grep -q '"IsTor":true' || exit 1

ENTRYPOINT ["tor", "-f", "/etc/tor/torrc"]
