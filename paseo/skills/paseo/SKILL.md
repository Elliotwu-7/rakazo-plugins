---
name: paseo
description: Inspect and operate the Paseo daemon on a connected computer through Device Control.
---

# Paseo Across Devices

Paseo runs on the user's Mac Mini. Use the `device-control` MCP server to reach it;
do not assume a localhost Paseo endpoint is reachable from the Rakazo container.

## Discover

1. Call `list_devices`.
2. Choose the Paseo host, normally `mac-mini`.
3. Verify the installed CLI and daemon with `run_command`. A known macOS path is:

```sh
/Applications/Paseo.app/Contents/Resources/bin/paseo status --json
```

Before constructing commands, run `paseo --help` and the relevant subcommand `--help`
on that exact host. The installed CLI version is the source of truth; do not assume a
command or flag exists merely because it appears in this skill.

## Run an agent

Common non-interactive forms include:

```sh
/Applications/Paseo.app/Contents/Resources/bin/paseo ls -g --json
/Applications/Paseo.app/Contents/Resources/bin/paseo inspect --json <agent-id>
/Applications/Paseo.app/Contents/Resources/bin/paseo send --json --no-wait <agent-id> "<message>"
```

For a new agent, inspect `paseo run --help` before constructing arguments. Use a
workspace path that already exists on the host. Do not create a second copy of the
same branch or project.

## Monitor

After `send`, poll the returned agent using only monitor commands confirmed by the
installed CLI help. Report the actual terminal status and relevant output. If the
daemon is not reachable, include the exact error and ask the user to check the Mac
Paseo app; an offline device cannot be controlled.

## Copy results

Use `read_file`, `list_files` or `copy_file` to bring requested artifacts back. Verify
the destination exists and report its path.
