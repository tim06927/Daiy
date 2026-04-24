# Local Production Deployment

This server runs Daiy behind Caddy on `app.daiy.de`. The hostname is centralized in `/etc/daiy/daiy.env` so it can later be changed to `snap-to-cart.daiy.de` without editing the app.

## Runtime

- systemd service: `daiy.service`
- app user: `tim`
- working directory: `/home/tim/git/Daiy`
- internal bind: `127.0.0.1:5001`
- reverse proxy: Caddy, public HTTPS on `$DAIY_PUBLIC_HOST`

## Files

- systemd unit source: `deploy/systemd/daiy.service`
- Caddy site source: `deploy/caddy/daiy.caddy`
- shared deployment env source: `deploy/env/daiy.env`
- installer: `deploy/install-local-production.sh`
- installed systemd unit: `/etc/systemd/system/daiy.service`
- installed deployment env: `/etc/daiy/daiy.env`
- installed Caddy env drop-in: `/etc/systemd/system/caddy.service.d/daiy-env.conf`
- installed Caddy config: appended to `/etc/caddy/Caddyfile`
- optional FlexDNS script: `/usr/local/sbin/update-flexdns-daiy`
- optional FlexDNS timer: `flexdns-daiy.timer`

## Install

```bash
sudo /home/tim/git/Daiy/deploy/install-local-production.sh
```

The installer enables `flexdns-daiy.timer` only if `/usr/local/sbin/update-flexdns-daiy` already exists and is executable.

## FlexDNS

Create `/usr/local/sbin/update-flexdns-daiy` from your existing FlexDNS updater or from `deploy/flexdns/update-flexdns-daiy.example`. It should source `/etc/daiy/daiy.env` and update the record named by `DAIY_PUBLIC_HOST`.

```bash
sudo install -m 0755 deploy/flexdns/update-flexdns-daiy.example /usr/local/sbin/update-flexdns-daiy
sudoedit /usr/local/sbin/update-flexdns-daiy
sudo systemctl enable --now flexdns-daiy.timer
```

## Operations

```bash
sudo systemctl status daiy
sudo journalctl -u daiy -f
sudo systemctl restart daiy
sudo systemctl reload caddy
```

## Switch Subdomain Later

1. Update FlexDNS/DNS so `snap-to-cart.daiy.de` points to this server.
2. Edit `/etc/daiy/daiy.env`:
   ```bash
   DAIY_PUBLIC_HOST=snap-to-cart.daiy.de
   DAIY_UPSTREAM=127.0.0.1:5001
   ```
3. Reload services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart caddy
   sudo systemctl restart daiy
   ```
