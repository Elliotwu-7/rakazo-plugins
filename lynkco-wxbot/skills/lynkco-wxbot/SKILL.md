---
name: lynkco-wxbot
description: Inspect and use the Windows WeChat lan_bridge through a connected device or a reachable tokenized bridge URL.
---

# Lynkco WeChat Bot

The safe entry point is the tokenized `lan_bridge`, normally on port `15040`.
Never connect directly to the WeChat hook port `30001` and never expose it publicly.

## Preconditions

1. Call `list_devices` and find the Windows bridge host.
2. If the host is online, use `run_command` to probe:

```sh
curl -fsS http://127.0.0.1:15040/health
```

3. Treat `/capabilities` as the runtime source of truth for authenticated routes and
   supported actions. The bridge token must come from Rakazo credentials or the device
   secret store; never place its value in chat or a command echoed to logs.

If no Windows host is connected, stop and report it as offline. Do not pretend the
bridge is available.

## Supported actions

The bridge may expose health, capability, session and send routes. Confirm each route
and request schema from `/capabilities` and its discovery output before calling it.
Common send categories are text, image and file.

For any send, show the exact target and message before sending. Require explicit
confirmation. Treat the bearer token as a secret and never echo it.

WeChat 4.x hooking is version-sensitive and may not support voice, video, quote,
forward, revoke or native emoji. Report runtime capabilities instead of inventing an
API.
