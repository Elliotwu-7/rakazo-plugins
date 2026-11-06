# Rakazo Plugins

Public Rakazo plugin manifests and skills for Elliot Wu's connected tools.

## Plugins

| Directory | Purpose |
| --- | --- |
| `device-control` | Authenticated cross-device MCP: list devices, run commands, read/write/copy files. |
| `paseo` | Operate Paseo on a connected Mac through `device-control`. |
| `github` | GitHub's official remote MCP server. |
| `wps-office` | WPS 365 cloud-document MCP (enterprise access token required). |
| `netease-mail` | Self-hosted NetEase Mail MCP adapter (IMAP/SMTP authorization code required); implementation is in `netease-mail-adapter/`. |
| `artex-god` | Authorized, read-only-first ARTEX workflow skill. |
| `lynkco-wxbot` | Operate the tokenized Windows `lan_bridge`, when that device is online. |
| `miaochat` | Read and send Miaochat messages through the same `lan_bridge`. |

Install a single plugin by pointing Rakazo at its GitHub tree URL, for example:

```text
https://github.com/Elliotwu-7/rakazo-plugins/tree/main/device-control
```

Credentials are never committed. Set them after installation in Rakazo's encrypted
Advanced MCP settings. The `device-control`, `github`, `netease-mail` and `wps-office` manifests declare
an empty `Authorization` header so Rakazo can show the credential field; a Bearer
or OAuth token is injected at runtime.

## Requirements

- The public MCP endpoints must be HTTPS and reachable from Rakazo.
- GitHub requires a bearer token or OAuth authorization.
- WPS requires a WPS 365 enterprise application, approved MCP permissions and an
  OAuth access token.
- NetEase Mail requires an official client authorization code, not the web login
  password.
- Windows messaging plugins require the Windows bridge to be online and reachable.
