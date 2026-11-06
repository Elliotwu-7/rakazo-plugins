---
name: artex-god
description: Operate an existing ARTEX installation for authorized, scoped security research with read-only defaults.
---

# ARTEX-God

ARTEX commonly runs on port `8787`. It is an operator tool, not a public service.
Use the `device-control` MCP server to inspect and operate the machine where ARTEX is
installed.

## Guardrails

- Require a clear authorized target and scope before reconnaissance.
- Start with passive or read-only actions.
- Do not perform exploitation, credential attacks, persistence, lateral movement,
  destructive writes, RF transmission, or OT/IoT control unless the user explicitly
  authorizes the exact action and scope.
- Never paste secrets, session tokens or private target data into a public plugin.
- Preserve evidence and report exact command output rather than guessing.

## Discovery

Call `list_devices`, then use `run_command` on the ARTEX host:

```sh
curl -fsS http://127.0.0.1:8787/health
ps aux | grep -i '[a]rtex'
```

If the service is down, report that fact. Do not silently build or redeploy a second
copy. Use the existing project checkout on that device.

## Workflow

1. Confirm authorization and target scope.
2. Inspect existing ARTEX projects/tasks and the configured ScopeSentry scope.
3. Use `api-recon`, `iot-protocols`, `mqtt-iov`, `satcom-recon` or `scopesentry`
   workflows only within that scope.
4. Prefer evidence collection and reporting.
5. Ask for explicit approval before any state-changing or high-risk step.
