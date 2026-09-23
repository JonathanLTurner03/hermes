# hermes (registry) — Project Overview

## Purpose

`hermes` is the fleet's answer to "what's supposed to be running where." It's a git repository, not a running program — its entire job is to hold, in one place, the Compose configuration for every service on every server, organized so that any host can pull down exactly its own slice and nothing else.

Where `hermes-cli` is the tool that *acts*, `hermes` is the thing that says what to act on.

## Core idea

One server, one directory. One service, one subdirectory under that. Config that's fine to share sits in tracked `.env` files; anything sensitive is either structurally excluded from the repo entirely or tracked only in encrypted form. The repo is meant to be readable top to bottom as an inventory: open it up, and you can see every server in the fleet and everything each one runs, without needing access to any of the actual machines.

## Goals

- **Single source of truth.** No host should ever have config for a service that isn't reflected in `hermes`. If it's running, it's because it's in the registry; if it's in the registry, that's what should be running.
- **Version-controlled infrastructure.** Changes to what a service does — a port remap, a new environment variable, a network change — go through git like any other change. History, blame, and rollback all come for free instead of being reconstructed from memory of what used to be true.
- **Safe to look at, unsafe to leak.** Anyone who can read this repo can see the shape of the whole fleet — what runs where — without being able to see a single secret value. Two tiers, both keep "can read the repo" from meaning "can read a secret": `.env.secrets` never gets committed at all (out-of-band, per-host); `secrets.enc.yaml` is tracked but encrypted at rest (sops+age), so even a full clone can't decrypt a value without the right host's private key.
- **Additive by design.** Bringing a new server online should mean adding a new top-level directory, not restructuring anything that exists. The same goes for adding a service to an existing server.

## How it's meant to work

A server's directory in `hermes` is a complete description of what that host runs: one subdirectory per service, each with its own Compose file and its own config. Shared, host-wide config lives at the server directory's root instead of being duplicated into every service.

The registry itself never runs anything and never talks to Docker. It's read by `hc` on each host, which resolves paths inside it and does the actual work. `hermes` doesn't need to know that `hc` exists, in principle — anything capable of reading a directory layout and a Compose file could consume it. In practice `hc` is the only thing that does.

Changes flow one way: someone edits a service's config in `hermes`, commits, pushes; the affected host runs `hc pull` and then re-applies whatever changed with `hc up`/`hc restart`. The registry never gets written to by anything running on the hosts themselves — it's upstream only.

## What "done" looks like

Someone unfamiliar with the fleet can clone `hermes`, and from directory names alone, know every server that exists and every service it runs — no wiki, no separate documentation, no asking around. A new server coming online is a new top-level directory and nothing else changing. A service moving from one host to another is deleting one directory and adding another, with git recording exactly when and why.

## Non-goals

- `hermes` doesn't hold secrets in plaintext, ever. Values tracked here at all (`secrets.enc.yaml`) are sops+age encrypted at rest, decryptable only by whichever hosts `.sops.yaml` lists as recipients for that path — anything not worth tracking even encrypted stays in an untracked `.env.secrets` instead.
- It's not a deployment pipeline. There's no CI here that pushes changes out automatically — a host only ever gets what's in `hermes` because it explicitly pulled.
- It doesn't express relationships between services (startup order, dependencies) — that's the supervisord layer's job, a separate concern from what the registry describes.
