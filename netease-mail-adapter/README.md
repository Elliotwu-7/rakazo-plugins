# NetEase Mail MCP adapter

A small, dependency-free Python 3 server that exposes NetEase 163 Mail over an
authenticated MCP Streamable HTTP endpoint. The public plugin repository contains no
account credentials.

## Tools

- `get_mail_status`
- `list_folders`
- `search_messages`
- `read_message`
- `send_email`

The adapter uses IMAP over TLS (`imap.163.com:993`) and SMTP over TLS
(`smtp.163.com:465`). NetEase requires an official client authorization code for
third-party mail clients. The normal web login password is not a substitute.

## Configuration

Set these environment variables, preferably through files mounted with mode `0600`:

| Variable | File variant | Purpose |
| --- | --- | --- |
| `MCP_HTTP_TOKEN` | `MCP_HTTP_TOKEN_FILE` | Bearer token required by the MCP endpoint; at least 32 characters |
| `MAIL_USERNAME` | `MAIL_USERNAME_FILE` | Full 163 Mail address |
| `MAIL_AUTH_CODE` | `MAIL_AUTH_CODE_FILE` | NetEase client authorization code |
| `MAIL_FROM` | `MAIL_FROM_FILE` | Optional From address; defaults to `MAIL_USERNAME` |
| `IMAP_HOST` | — | Defaults to `imap.163.com` |
| `IMAP_PORT` | — | Defaults to `993` |
| `SMTP_HOST` | — | Defaults to `smtp.163.com` |
| `SMTP_PORT` | — | Defaults to `465` |
| `MCP_HTTP_HOST` | — | Defaults to `127.0.0.1` |
| `MCP_HTTP_PORT` | — | Defaults to `3197` |

## Run

```sh
python3 server.py
```

The MCP endpoint is `http://127.0.0.1:3197/mcp`; `GET /health` is unauthenticated
and only reports whether credentials are present. Bind the service to loopback and
terminate TLS at Caddy or another trusted reverse proxy.

## Safety behavior

- Search and read use UIDs.
- Reading does not mark a message as seen unless `mark_seen=true`.
- Message bodies above 5 MiB are rejected.
- Search results are capped at 50.
- Sending requires `confirm=true`; recipients, subject and body are validated.
- Credentials and authorization codes are never returned by a tool.
