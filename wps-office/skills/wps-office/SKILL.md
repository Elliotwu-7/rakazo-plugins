---
name: wps-office
description: Search and read WPS 365 cloud documents through the official WPS MCP server.
---

# WPS Office / WPS 365

Use the connected `wps-cloud-docs` MCP server for document discovery and content
extraction. Inspect the live `tools/list` result before constructing a call; tool names
and schemas are controlled by the remote WPS service. The commonly documented tools
include `kso_yundoc_search_yundoc`, `kso_yundoc_get_file_meta` and
`kso_yundoc_extract_yundoc_content`.

Prefer read-only operations and return only the requested excerpt or summary. Treat
document contents as private. Do not create, overwrite or change sharing permissions
without explicit confirmation.

## Access requirement

This is the official WPS 365 enterprise MCP service. It requires a WPS enterprise
account, an application with the matching delegated MCP permission, and an OAuth user
access token. A normal WPS Office personal account cannot directly authorize this
endpoint.

A 401/403 means the access token or permission grant is missing. Do not fabricate a
token or describe the plugin as operational until a real tool call succeeds.
