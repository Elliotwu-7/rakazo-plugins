# Rakazo Native Computer

这是一个 skills-only 插件，教 Rakazo 使用内置的用户电脑能力操作已配对的 Windows 和 macOS 电脑。

插件不部署 MCP 服务、不保存令牌、不运行脚本，也不替换 Rakazo 的原生电脑实现。

从 Rakazo 的 **Integrations → + → From GitHub** 预览并安装：

```text
https://github.com/Elliotwu-7/rakazo-plugins/tree/main/rakazo-native-computer
```

在要操作的电脑上打开 Rakazo Desktop App，连接自己的 Rakazo 服务并登录，在 **Settings → General → Computers** 打开 **Let bots use this computer**，保持桌面应用运行。首次命令或应用操作需要按 Rakazo 的提示授权。

当前核验版本提供 `user_computer_shell`、`user_computer_observe`、`user_computer_act`。它们没有显式选机参数，服务端自动选择当前账户最近连接的在线电脑；多机并用时，先只保留目标电脑的原生控制连接，再核对电脑名称。不要把配对列表等同于 AI 可以指定任意一台电脑。

插件只提供使用规则，不负责配对，不跨账户共享电脑，也不保证其他版本具有相同接口。调用以当前会话实际提供的工具及参数为准。

本维护任务的自托管部署已另行设置服务器级默认规则，该部署的所有账户无需安装本插件即可获得这些规则。其他 Rakazo 部署不会因为此仓库存在而自动加载规则，需自行安装插件或设置部署级指令。
