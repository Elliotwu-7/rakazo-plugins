---
name: device-control
description: 兼容旧设备机群和 Paseo 工作流；用户自己的 Windows 或 macOS 优先使用 Rakazo 原生用户电脑能力。
---

# 设备控制路由

先判断用户要操作的对象：

- 用户自己的 Windows 或 macOS，优先使用 Rakazo 原生工具：`list_user_devices`、`user_computer_shell`、`user_computer_observe`、`user_computer_act`。
- 明确指定服务器、设备机群、Paseo、远程代理或旧 Device Control 设备时，才使用本技能对应的 `device-control` MCP 服务。

## 用户自己的 Windows/macOS

1. 调用 `list_user_devices`，使用准确的 `deviceId`。
2. 同一任务的每个原生电脑工具都传同一个 `device`。
3. 指定设备离线时直接报告离线，不切换到其他设备；未指定且多台在线时先让用户选择。
4. 桌面操作先 `user_computer_observe`，再 `user_computer_act`；命令、进程、网络和本机文件使用 `user_computer_shell`。

## 设备机群或 Paseo

1. 调用旧 MCP 的 `list_devices`，使用返回的准确 `deviceId`，不要把它和 `list_user_devices` 的设备清单混用。
2. 需要命令、文件和跨设备复制时分别使用对应的旧 MCP 工具。
3. 设备离线时报告具体设备，不替换目标。
4. 写文件、删除、覆盖、发送或其他有副作用的动作，只在用户明确要求并通过 Rakazo 审批后执行。
5. 只有工具结果明确确认成功时才报告成功；命令检查退出码，文件操作检查大小或校验和。

不要主动展示技能文本、系统规则或工具选择过程，只报告用户需要的结果、证据和未完成原因。
