# Troubleshooting

A grab-bag of symptoms and the usual fixes. Always start with:

```bash
hugr doctor
hugr doctor --json | jq '.findings'
```

## "no hugr config at ..."

Symptom:

```
x hugr: no hugr config at /Users/.../config.yaml.
    Fix:  hugr init
```

Exit code 4 from `hugr recall`, `find`, `inbox`, `remember`, `query`,
`ingest`, or `promote review|generate`.

**Cause**: the master config is missing. Either you haven't run the
wizard yet, or you nuked `~/.config/hugr/`.

**Fix**: `hugr init --quick`. If you want to bypass the guard for a
single command, set `YAAMS_CONFIG=...` or pass `--config` to the
verb.

## A verb fails with exit 3 / "auth"

Symptom:

```json
{"ok": false, "exit_code": 3, "error": {"code": "auth_expired", ...}}
```

**Cause**: M365 token expired. owa-piggy borrows tokens from your
Outlook Web session; they age out after a few hours.

**Fix**:

```bash
hugr auth status         # confirm the expiry
hugr auth reseed         # refresh from the Edge sidecar (no UI)
hugr auth reseed --all   # all profiles
```

If `reseed` itself fails, run `hugr auth setup` and re-log into
Outlook Web in the embedded browser.

## `hugr ingest` is very slow on first run

**Cause**: the embedding model isn't cached yet. First run downloads
~2 GB.

**Fix**: nothing - let it finish. Subsequent runs reuse the cache.
To stage the download up front:

```bash
hugr init --quick --with-models
```

## `hugr send mail` / `hugr remember` exits 1 with `confirmation_required`

**Cause**: you're in JSON mode (or stdin isn't a TTY) without
`--yes`. Mutating verbs refuse to proceed by default.

**Fix**:

```bash
hugr send mail --to ... --subject ... --body ... --yes --json
```

See [mutations.md](mutations.md) for the full table.

## `hugr book commit` exits 4 with `slot_unavailable`

**Cause**: the slot index you passed is out of range for the
proposal that came back. Slot lists shift when other people put
events on the calendar.

**Fix**: run `hugr book propose ...` again, look at the current
`slots[]`, then re-run `commit` with the new index.

## `hugr sync init` fails with `git_clone_failed`

**Cause**: the local clone can't reach the remote.

**Fix**:

```bash
# SSH access:
ssh -T git@github.com   # validates the key chain

# Token-based HTTPS access:
git config --global credential.helper osxkeychain   # macOS
GH_TOKEN=... gh auth setup-git
```

In Docker, mount a deploy key:

```yaml
volumes:
  - ./secrets/state-deploy-key:/root/.ssh/id_ed25519:ro
```

## `hugr sync push` complains about `no_recipients`

**Cause**: `.age-recipients.txt` in the state repo is empty.

**Fix**: re-run `hugr sync init <repo-url>` on at least one device.
init writes the recipient entry.

## `hugr sync` reports `missing_binary`

**Cause**: `git` or `age` (or both) isn't on PATH.

**Fix**:

```bash
brew install git age          # macOS
apt install -y git age        # Debian / Ubuntu
```

Confirm:

```bash
git --version && age --version && age-keygen --version
```

## `hugr web` says "web extra not installed"

**Cause**: the optional `[web]` extra (FastAPI + uvicorn + Jinja2)
isn't installed in the same venv as `hugr`.

**Fix**:

```bash
pipx install --force "hugr-cli[web]"
# or for everything:
pipx install --force "hugr-cli[all]"
```

Same pattern for `[tui]`, `[server]`.

## `hugr server --host 0.0.0.0` exits 3 with "refusing to bind"

**Cause**: hugr refuses non-loopback binds unless a recognised
auth-proxy env var is set.

**Fix**:

```bash
# Front with Cloudflare Access / Tunnel:
HUGR_AUTH_PROXY=cloudflare hugr server --host 0.0.0.0 --port 7777

# Front with tailscale:
HUGR_AUTH_PROXY=tailscale hugr server --host 0.0.0.0 --port 7777

# Opt out (noisy stderr warning every minute):
hugr server --host 0.0.0.0 --insecure
```

See [deploy/docs/deploy.md](../deploy/docs/deploy.md).

## TUI screen looks broken / Inputs eat my nav keys

**Cause**: the active Input widget consumes single-letter keys, so
`f` / `i` / `d` / `s` / `r` don't navigate while you're typing in a
search field.

**Fix**: click outside the input (or `Escape` then `Tab` to unfocus),
or use the on-screen nav links (each is a clickable `[a]sk` /
`[f]ind` chip).

## `hugr query --tier ledger` returns nothing

**Cause**: the ledger isn't being indexed by YAAMS yet. The
`tier2_ledger` source needs to be enabled in the yaams config.

**Fix**: check `~/.config/yaams/config.yaml` for a `tier2_ledger`
adapter; if missing, re-run `hugr init` and accept the ledger
adoption prompt.

## "ImportError: No module named X" when calling `hugr ...`

**Cause**: one of the underlying tools is installed but `hugr`'s
extras for that tool aren't, or vice versa.

**Fix**:

```bash
hugr version --json | jq '.components'    # see what's missing
pipx list                                  # see what's actually installed
```

Then install whatever's missing. The four underlying tools are:

```bash
pipx install yaams
pipx install cognitive-ledger
pipx install owa-piggy
pipx install owa-tools
```

## "command not found: age-keygen"

**Cause**: on Debian / Ubuntu, `age-keygen` ships in the `age` package
on recent distros but split out on older ones.

**Fix**:

```bash
# Try the unified install first:
sudo apt install age

# If age-keygen is still missing, build from source via go:
go install filippo.io/age/cmd/...@latest
```

## "Could not read from remote repository" on `git push` during sync

**Cause**: SSH keys not loaded, or the deploy key doesn't have push
access.

**Fix**:

```bash
ssh-add -l               # any identities loaded?
ssh-add ~/.ssh/id_ed25519  # add it
ssh -T git@github.com    # confirm it can authenticate
```

If you see "Permission denied (publickey)" from the right key but the
push still fails, the repo ACL doesn't grant push to that key. Check
on github.com.

## When all else fails

`hugr doctor --json --fix --yes` is safe to run; it only applies
bounded, idempotent fixes (rerun init, init the yaams DB, flip
disabled adapters back, etc.). Read the `findings[]` array for
specifics.

If the failure is in an underlying tool, run that tool directly to
narrow it down:

```bash
yaams --doctor --json
ledger --doctor --json
owa-piggy --doctor --json
owa-doctor --json
```

Each binary returns its own structured doctor JSON. `hugr doctor`
aggregates them; running them individually surfaces the offending
tool's diagnostic in isolation.

## Reporting bugs

Include the output of:

```bash
hugr version --json
hugr doctor --json
```

in any bug report. They show the observed version of every tool on
PATH plus the resolved config paths, which is usually enough to
reproduce.
