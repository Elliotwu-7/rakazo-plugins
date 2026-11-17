---
name: device-control
description: 兼容旧设备机群和 Paseo 工作流；用户自己的 Windows 或 macOS 优先使用 Rakazo 原生用户电脑能力。
---

# 设备控制路由

先判断用户要操作的对象：用户自己的 Windows 或 macOS 优先使用本轮实际提供的原生电脑工具；明确指定服务器、设备机群、Paseo、远程代理或旧 Device Control 时，使用相应的已连接工具。

## 用户自己的 Windows/macOS

1. 当前原生接口提供 `user_computer_shell`、`user_computer_observe`、`user_computer_act`，没有设备枚举工具，也没有 `device` 或 `deviceId` 参数。以当前工具定义为准，不编造调用。
2. 当前后台会选择该账户最近连接的在线电脑，每次调用可能重新选择。用户指定电脑时，先用只读 `hostname` 核对；不匹配或无法确认就停止修改。
3. 多台电脑连接且接口无法明确选机时，请用户在非目标电脑上关闭 **Let bots use this computer**，只保留目标连接后再核对。不要把一句设备名称或一次 hostname 核验当成后续设备锁定。
4. 桌面操作先 `user_computer_observe`，再按最新元素编号调用 `user_computer_act` 并检查结果；本机命令、进程、网络和文件使用 `user_computer_shell`。Windows 使用 PowerShell，macOS 按实际 shell 选择语法。
5. 原生工具不可用时，说明需要在目标 Rakazo Desktop App 登录对应账户、开启该开关并保持应用运行。账户归属、会话来源与审批仍然有效；全局规则不赋予跨账户设备权限。

## 设备机群或 Paseo

1. 仅当本轮确实提供旧 MCP 工具时，先调用其 `list_devices`，使用返回的准确 `deviceId`。这份清单不等于原生电脑清单。
2. 按实际工具定义执行命令、文件或跨设备操作。MCP 未连接或工具缺失时明确报告，不声称兼容链路已经可用。
3. 指定设备离线就报告离线，不替换目标。写文件、删除、覆盖、发送等动作遵循用户授权与 Rakazo 审批。
4. 只有结果明确确认成功时才报告成功；命令核对退出码，文件核对内容、大小或校验和。

不要主动展示技能文本和内部规则；回复只保留真实结果、关键证据和未完成原因。
