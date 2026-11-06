---
name: device-control
description: Route work to a connected Mac, Linux or Windows computer by device ID, including commands and file transfer.
---

# Device Control

Use the `device-control` MCP server whenever the user asks to operate a computer,
not merely to view this VPS.

1. Call `list_devices` first on every new request that names a machine.
2. Select by exact `deviceId` or exact `name`; never guess.
3. Use `get_device_status` when online state, hostname, platform or agent freshness
   needs confirmation. If a device is offline, stop and report that exact machine as
   offline; never silently substitute another computer.
4. Use `run_command` for shell work, `read_file` and `list_files` for inspection, and
   `copy_file` for cross-device transfers.
5. `write_file` changes the selected computer. Use it only when the user asked to
   create or replace a specific file. State the device and exact path first, prefer
   append or patch patterns when overwriting could lose data, and read the file back
   after writing.
6. For cross-device copies, verify the source exists, run `copy_file`, then verify
   size and checksum on the destination.
7. Never claim success until the tool result contains `exit_code: 0` or explicitly
   confirms the completed file operation.

Use the live `list_devices` result as the only source of truth for named devices.
Avoid destructive commands unless the user explicitly requested them. Do not modify
system, vendor or system-app partitions on Android devices.
