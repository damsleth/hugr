# Sync - cross-device state

`hugr sync` keeps the master config (and, in a follow-up, the YAAMS
DB + owa-piggy tokens) in step across the devices you use. It's a
thin layer over two binaries you probably already have:

- `git` - transport. The state lives in a private GitHub repo you
  control (e.g. `damsleth/hugr-state`).
- `age` - encryption at rest. Every file in the state repo is
  encrypted to every device's public key.

If either binary is missing on PATH, `hugr sync` returns an envelope
with `error.code = "missing_binary"` and exit 4. `hugr doctor`
surfaces the gap on the relevant device.

## The mental model

```
        ┌─ laptop ──┐    ┌─ damsleth/hugr-state ──┐    ┌─ VPS ──────┐
        │  encrypt  │ -> │   age-encrypted blobs   │ <- │  decrypt   │
        │  push     │    │   per-device folders    │    │  pull      │
        └───────────┘    └─────────────────────────┘    └────────────┘
```

Two folders inside the repo:

- `shared/` - things every device writes/reads. Today this is just
  the master hugr config; the YAAMS DB and tool configs land here in
  04.4.
- `devices/<device-id>/` - per-device snapshots (push timestamps,
  per-device logs). One folder per machine; merge conflicts avoided.

Every blob is suffixed `.age`; the `age-recipients.txt` file at the
repo root lists every device's public key, one per line.

## First-time setup on each device

```bash
# 1. Create the state repo (do this once, on GitHub).
#    Suggested name: damsleth/hugr-state. Private.

# 2. Init the local clone + register this device.
hugr sync init git@github.com:you/hugr-state.git
```

What `init` does:

1. Clones the repo into `$HUGR_STATE_DIR` (default
   `$HUGR_HOME/state`).
2. Generates an age identity at `<repo>/.age/identity.key` (mode 0600)
   if one isn't already there. Reused on re-runs.
3. Reads the public key out of the identity.
4. Adds (or replaces, for the same device id) a line in
   `.age-recipients.txt` shaped `<public_key> # <device-id>`.

Result envelope:

```json
{
  "tool": "hugr",
  "command": "sync init",
  "ok": true,
  "exit_code": 0,
  "repo_url": "git@github.com:you/hugr-state.git",
  "clone_into": "/Users/you/.local/share/hugr/state",
  "identity_path": "/Users/you/.local/share/hugr/state/.age/identity.key",
  "device_id": "you-at-laptop-snaroya",
  "public_key": "age1...",
  "error": null
}
```

`init` is idempotent. Re-running it on the same device only refreshes
the recipient entry.

### About `device_id`

By default it's `$USER@$HOSTNAME` sanitised to `lower-case-and-dashes`.
Override with `HUGR_DEVICE_ID`:

```bash
HUGR_DEVICE_ID=vps-fly-osl hugr sync init git@github.com:you/hugr-state.git
```

Useful when two machines share a username or when a container runs
as root.

### About `HUGR_STATE_DIR`

Override the clone location:

```bash
HUGR_STATE_DIR=/srv/hugr/state hugr sync init git@github.com:you/hugr-state.git
```

The Docker image's `/state` volume sets this for you.

## Inspecting the state

```bash
hugr sync status
hugr sync status --json
```

Output:

```json
{
  "tool": "hugr",
  "command": "sync status",
  "ok": true,
  "exit_code": 0,
  "clone_into": "/Users/you/.local/share/hugr/state",
  "device_id": "you-at-laptop-snaroya",
  "public_key": "age1...",
  "recipients": [
    {"device": "you-at-laptop-snaroya", "public_key": "age1..."},
    {"device": "vps-fly-osl", "public_key": "age1..."},
    {"device": "phone-iphone", "public_key": "age1..."}
  ],
  "last_commit": {
    "sha": "abc1234...",
    "author": "you",
    "date": "2026-05-25 12:00:00 +0200",
    "subject": "sync push from laptop-snaroya @ 2026-05-25T10:00:00Z"
  }
}
```

The `--pretty` rendering is the same data laid out for humans.

## Push

Snapshot opt-in state on this device, encrypt, commit, push.

```bash
hugr sync push --yes
hugr sync push --yes --message "after kickoff"
hugr sync push --yes --json
```

Today the snapshot list is:

- `shared/hugr/master-config.yaml.gz.age` (master config gzip + age)

(yaams DB + tool configs + owa-piggy token bundles land in 04.4.)

The commit message defaults to
`sync push from <device-id> @ <ISO8601>`; override with `-m`.

Per-device metadata is written to
`devices/<device-id>/last-push.json` so other devices can see when
this device last contributed.

`--yes` is required when `--json` is set or when stdin is not a TTY -
same rule as the other mutating verbs (see [mutations.md](mutations.md)).

### Failure shapes

Network / auth fail at git push:

```json
{
  "tool": "hugr",
  "command": "sync push",
  "ok": false,
  "exit_code": 2,
  "error": {
    "code": "git_push_failed",
    "message": "git push failed (exit 1)",
    "hint": "remote: Permission denied (publickey)..."
  },
  "snapshots": ["shared/hugr/master-config.yaml.gz.age"]
}
```

Repo not provisioned yet:

```json
{
  "tool": "hugr",
  "command": "sync push",
  "ok": false,
  "exit_code": 4,
  "error": {
    "code": "not_initialized",
    "message": "no state repo at /Users/.../state",
    "hint": "Run `hugr sync init <repo-url>` first."
  }
}
```

Missing binary:

```json
{
  "ok": false,
  "exit_code": 4,
  "error": {
    "code": "missing_binary",
    "message": "missing binary on PATH: age",
    "hint": "Install with `brew install age git` (macOS) or your package manager."
  }
}
```

## Pull

Fast-forward the local clone. **Snapshot writeback** (decrypt + apply
to local configs / DB) is deferred to plan 04.4; today `pull` only
updates the git working tree.

```bash
hugr sync pull
hugr sync pull --json
```

```json
{
  "tool": "hugr",
  "command": "sync pull",
  "ok": true,
  "exit_code": 0,
  "pulled_at": "2026-05-25T12:10:00Z",
  "last_commit": {"sha": "...", "subject": "..."},
  "note": "snapshot writeback is deferred to plan 04.4"
}
```

## Recommended cadence

There is no built-in scheduler. Add a systemd timer, launchd plist,
or cron job for the cadence you want. Example launchd plist (macOS):

```xml
<!-- ~/Library/LaunchAgents/com.damsleth.hugr-sync.plist -->
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.damsleth.hugr-sync</string>
    <key>ProgramArguments</key>
    <array>
      <string>/opt/homebrew/bin/hugr</string>
      <string>sync</string>
      <string>push</string>
      <string>--yes</string>
      <string>--json</string>
    </array>
    <key>StartInterval</key><integer>3600</integer>
    <key>StandardErrorPath</key><string>/tmp/hugr-sync.err</string>
  </dict>
</plist>
```

systemd timer for Linux is in [deploy/systemd/hugr.service](../deploy/systemd/hugr.service)
- pair it with a `.timer` for the sync cadence.

## Threat model

- **Anyone with read access to the state repo** sees only the
  encrypted blobs and the public-key recipient list. The recipient
  list reveals device names and public keys; nothing else.
- **Anyone with a current device identity** (the `.age/identity.key`
  on a particular machine, mode 0600) can decrypt every blob.
- **Anyone with push access to the state repo** can rotate the
  recipient list to add their own key. Treat the repo's write ACL
  the same way you'd treat root on every synced device.

age (filippo.io/age) is the encryption primitive. Public keys are
short and human-comparable; private keys never leave the device that
generated them.

## What is NOT yet synced

- YAAMS SQLite DB. Plan 04.4 adds an hourly snapshot with delta
  compaction (the full dump is too big for a per-hour commit cycle).
- owa-piggy refresh tokens. Plan 04.4 ships a `hugr auth export-bundle`
  / `import-bundle` flow over age.
- cognitive-ledger notes. They already sync via your existing notes
  repo - the state repo is for things that *can't* live in a public
  repo.
- `~/.config/<tool>/config.yaml` for each tool. Adopted on init but
  not snapshotted - users typically want per-device tool config (eg
  different ingest source paths).

See [`AUDIT.md`](../AUDIT.md) for the open upstream items required
before 04.4 can land cleanly.
