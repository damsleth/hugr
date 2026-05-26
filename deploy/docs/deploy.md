# Deploying `hugr server`

`hugr server` is a single FastAPI process that serves the web UI at
`/` and JSON mirrors at `/api/*`.

It binds to loopback by default. Anything non-loopback must go behind
one of:

- **Cloudflare Access / Tunnel** — recommended for "available
  everywhere" Plan 04 deployments. Set `HUGR_AUTH_PROXY=cloudflare`.
- **Tailscale** — simplest single-operator option. Set
  `HUGR_AUTH_PROXY=tailscale`.
- **Caddy / nginx + basic-auth or OIDC** — anything that terminates
  TLS and emits known forwarded-auth headers; still requires
  `HUGR_AUTH_PROXY` to be set to a recognized value.

Without a recognized proxy, `hugr server --host 0.0.0.0` refuses to
start (exit 3). Add `--insecure` to override; the process prints a
warning every 60s while running.

## 1) Docker (recommended)

```bash
docker run --rm -it -p 127.0.0.1:7777:7777 \
  -v hugr-config:/config \
  -v hugr-data:/data \
  -v hugr-state:/state \
  ghcr.io/damsleth/hugr:dev
```

Or with compose — copy `deploy/docker/docker-compose.example.yml`,
set `HUGR_AUTH_PROXY`, and `docker compose up -d`.

The image installs `git` and `age` so `hugr sync` works without extra
setup. State (`/state`) is meant to be a clone of your private
`damsleth/hugr-state` repo; provision it like this:

```bash
docker exec -it hugr hugr sync init git@github.com:you/hugr-state.git
```

## 2) Systemd on a VPS

```bash
useradd --system --create-home --home-dir /var/lib/hugr --shell /usr/sbin/nologin hugr
sudo -u hugr pipx install "hugr-cli[server,web]"
sudo cp deploy/systemd/hugr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hugr
```

The unit binds loopback at `127.0.0.1:7777` by default. Put Caddy in
front to terminate TLS:

```caddyfile
hugr.example.com {
  reverse_proxy 127.0.0.1:7777
}
```

If you front with Cloudflare Tunnel, set `HUGR_AUTH_PROXY=cloudflare`
in the unit file and bind `--host 0.0.0.0` so the tunnel can reach
the listener inside the VPS.

## 3) Tailscale

Set the unit to bind 0.0.0.0 and trust the tailnet:

```ini
Environment=HUGR_AUTH_PROXY=tailscale
ExecStart=/usr/local/bin/hugr server --host 0.0.0.0 --port 7777
```

Tailscale's per-device ACLs are the only auth here; treat the listener
the same way you'd treat any service you'd put on a tailnet.

## Healthcheck

`GET /healthz` returns `{"ok": true, "tool": "hugr"}` while the
process is up. The Docker image's `HEALTHCHECK` directive uses this
endpoint; set the same in your reverse proxy.

## What this deploy *does not* include

- Auth implementation. The operator brings Cloudflare Access /
  tailscale / basic-auth; `hugr server` only exposes the `HUGR_AUTH_PROXY`
  contract for "I trust the proxy in front of me".
- TLS termination. Caddy / Cloudflare / your reverse proxy handles it.
- Cron-driven `hugr sync push`. Add a systemd timer or a host cron
  that runs `hugr sync push --yes --json` on the cadence you want
  (defaults: hourly for DB, on-change for configs — see plan 04.3).

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Container exits with `refusing to bind` | Missing or unrecognized `HUGR_AUTH_PROXY` while binding non-loopback. Set it to `cloudflare` / `tailscale`, or pass `--insecure`. |
| `hugr sync init` fails with `git_clone_failed` | Container can't reach the state repo. Mount a deploy key or use HTTPS + a token. |
| `age-keygen` not found | Image / host is missing the `age` binary. `apt install age` / `brew install age`. `hugr doctor` flags this. |
