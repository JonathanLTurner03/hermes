# hermes — Fleet Configuration Registry

This repo is the source of truth for what runs on each host in the fleet: Docker Compose services and systemd mounts. Hosts don't carry their own config — they pull it from here via [`hc`](../hermes-cli) (the Hermes CLI) and apply it locally.

If you're looking for `hc`'s own command reference (`hc up`, `hc mount sync`, etc.), see the hermes-cli repo's README. This one covers how *this* repo is structured and how to add things to it.

## Layout

```
hermes/
└── <server>/                        # one directory per host, name matches `hc init <server>`
    ├── .env                         # optional, host-wide compose env (tracked)
    ├── .env.secrets                 # optional, host-wide secrets (NOT tracked — see below)
    ├── pools.yml                    # optional, names/mount points of this host's fstab-managed pools
    ├── <service>/
    │   ├── docker-compose.yml       # required
    │   ├── .env                     # optional, service-specific (tracked)
    │   └── .env.secrets             # optional, service-specific secrets (NOT tracked)
    └── mounts/
        └── <name>.yml               # optional, one systemd mount spec per file
```

`<server>` must match exactly what's passed to `hc init <server>` on that host — that's how `hc` knows which directory here is "its" config.

## Adding a compose service

1. Create `<server>/<new-service>/docker-compose.yml`.
2. If the service needs a network owned by another stack, declare it `external: true`:
   ```yaml
   networks:
     shared:
       external: true
   ```
   `hc up` creates it automatically (`docker network create`) if it doesn't exist yet — you don't need to pre-create it anywhere.
3. If the service needs secrets, reference `.env.secrets` as an `env_file:` in the compose file. **Never commit `.env.secrets`** — it's gitignored on purpose (see `.gitignore`). Get it onto the host out of band (scp, a secrets manager, whatever your process is) before starting the service — `hc up` refuses to start a service that declares `.env.secrets` but has none present on disk, rather than silently starting without it.
4. On the host: `hc pull && hc up <new-service>`.

## Adding a mount

Mounts are systemd `.mount` units rendered from a declarative spec here — you never hand-write the unit file, and it never lives in this repo either.

```yaml
# <server>/mounts/srv-jellyfin-media.yml
name: srv-jellyfin-media       # required — the friendly name used in `hc mount` commands
source: /mnt/pool/media        # required — becomes the unit's `What=`
target: /srv/jellyfin/media    # required — becomes the unit's `Where=`. The actual systemd unit
                                # filename is derived from THIS path (via systemd-escape), not from
                                # `name` — that's a systemd requirement, not a hermes-cli quirk.
type: bind                     # optional, default "bind"; also supports fuse.mergerfs, ext4, etc.
options: []                    # optional, list of mount options
depends_on: mnt-pool           # optional — name of another mount registered for this host;
                                # rendered as After=/Requires= on that mount's unit
description: "Jellyfin media bind mount"   # optional — shown in `hc mount status` and the unit's Description=
```

**Storage pools never get a spec file here.** Each pool stays in `/etc/fstab` on the host, unmanaged by `hc`, specifically so a mistake in this registry (or in `hc`) can only ever affect the derivative bind mounts, never the pool itself. A host declares its pools' names and mount points in an optional `<server>/pools.yml` instead:

```yaml
# <server>/pools.yml
pools:
  - name: mnt-pool
    target: /mnt/pool
  - name: mnt-pool2      # a host can have more than one independent pool
    target: /mnt/pool2
```

`hc mount sync` will reject a `mounts/<name>.yml` file whose `name` collides with an entry in `pools.yml`. Other mounts can still declare `depends_on: mnt-pool` (or `mnt-pool2`, etc.) — `hc` always assumes `<name>.mount` exists on the host via fstab for every pool listed there.

On the host, after adding or changing a spec:

```
hc pull
hc mount sync              # renders/updates unit files + regenerates the docker.service drop-in;
                            # doesn't start anything by itself
hc mount enable <name>      # or: hc mount sync --apply, to enable everything just added/changed
hc mount status             # table of every mount registered for this host, plus mnt-pool itself
```

To remove a mount: `hc mount disable <name>` on the host **first**, then delete `mounts/<name>.yml` here, `hc pull`, then `hc mount sync`. Sync refuses to delete the unit file for a mount that's still active unless `--force` is passed.

Docker on each host is wired to wait for every mount registered for it before starting, via a drop-in `hc mount sync` regenerates on every run. If that drop-in changes, `hc` will say so and tell you to re-run with `--restart-docker` to actually apply it — that bounces every container on the host, so it's never automatic.

See `mount-feature-doc.md` in the hermes-cli repo for the full design rationale behind these decisions (why the pool is excluded, how dependency ordering and the staleness check work, open questions considered during design).

## Workflow summary

1. Edit this repo — add or change a service directory or a `mounts/*.yml` spec.
2. Commit and push.
3. On the target host: `hc pull`, then `hc up <service>` and/or `hc mount sync` (+ `enable`/`--apply`) as needed.

## Secrets

Anything named `.env.secrets` (service-level or host-level, per the layout above) is gitignored and must never be committed. It's expected to already exist on each host out of band before `hc up` is run for a service that needs it — `hc` will tell you exactly which file it's missing and where it expects to find it.
