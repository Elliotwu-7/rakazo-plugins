---
name: github
description: Use GitHub's official MCP tools to inspect repositories, issues, pull requests, code and Actions.
---

# GitHub

The connected GitHub MCP endpoint is remote and its tool set can change. Call
`tools/list` (or use the tools exposed by Rakazo) as the source of truth for current
tool names and schemas.

1. Start with the current identity tool, commonly `get_me`, when account context matters.
2. Prefer read tools first, such as repository search, file reads, issue listing and
   code search.
3. Use pagination and minimal output where supported. Do not dump large API results
   into chat.
4. Before a write, state the exact owner, repository, branch, title or path and wait
   for the user's confirmation when the request is ambiguous.
5. Never force-push, delete a repository, rotate secrets or merge unless explicitly
   requested.
6. Report the authenticated account only as the GitHub login, never expose a token.

A 401 means the Rakazo GitHub MCP credential is missing, expired, or lacks the
required scope. Configure a GitHub bearer token or complete OAuth in Advanced MCP
settings; never put a token in a plugin manifest or skill.
