# 本机进度（WeChatAgent v0.4.0）

> 快照时间：2026-10-25 22:40　｜　记录人：DSH 助手
> 这份文档只记录**本机部署状态**，不含任何令牌、密钥或聊天内容。

## 1. 安装位置

| 项目 | 路径 |
| --- | --- |
| 程序 | `D:\zlh‘s program\app\WeChatAgent.exe`（v0.4.0） |
| 数据 | `D:\zlh‘s program\data\`（`workspace` / `runtimes` / `desktop`） |
| 配置 | `D:\zlh‘s program\data\workspace\config\wechatagent.json` |
| 匹配微信 | `D:\zlh‘s program\data\workspace\state\hook\wechat-4.1.10.27\Weixin.exe`（**4.1.10.27**） |
| 本机自己的微信 | `D:\zlh‘s program\Weixin\Weixin.exe`（4.1.15.56，**不能**用来跑机器人） |
| 微信数据根 | `D:\zlh‘s program\xwechat_files\` |
| DSH | `D:\zlh‘s program\dsh\DeepSeek Harness.exe` |

## 2. 两个微信账号

| 账号 | wxid | 用途 |
| --- | --- | --- |
| 主号 | `wxid_qfx9h2yxnubm22_35e7` | 日常使用，放手机 |
| 小号 | `wxid_2oks5madp2fd12_8ffe` | **接 AI**，登在 4.1.10.27 客户端里 |

同一台电脑同一时间只能登一个号；项目启动脚本检测到"另一个桌面微信在运行"会拒绝启动。

## 3. 已经打通的环节

- [x] 微信 hook 注入成功（`version.dll`，端口 `30001`，`startupState: ready`）
- [x] 账号目录识别：必须选到 `xwechat_files\wxid_xxx` 这一层（选上一级会命中"多账号"分支并清空路径）
- [x] 数据库密钥抓取 + 数据库校验通过（"matching version and selected account database verified"）
- [ ] DSH 桥接插件安装（阻塞点：`DSH_PLUGIN_NOT_READY`，插件未在 DSH 中安装/启用）
- [ ] 启动服务（等上一步）
- [ ] 绑定允许的聊天、人格、表情池

## 4. 已知坑（踩过的）

1. **「自动查找账号」永远找不到**：它只扫 `Documents`、家目录、OneDrive 和注册表 `FileSavePath`，**不扫 D 盘**。必须手动「选择文件夹」。
2. **多账号时路径被清空**：选 `xwechat_files` 会识别出 2 个账号，界面随后把路径清空；再点「识别此目录」就退化成自动扫描 → 报"未找到"。正解是**直接选到 `wxid_xxx` 这一层**。
3. **抓密钥必须在"未登录"状态**：密钥只在登录那一刻派生，先登录好再点连接必然 `READER_SETUP_TIMEOUT`。顺序：退出登录 → 点连接 → 立刻扫码。
4. **版本必须 4.1.10.27**：hook 与 native 组件都按这个版本编译，本机 4.1.15.56 会被判 `HOOK_VERSION_MISMATCH`。
5. **路径里有弯引号**：`D:\zlh‘s program\` 中 `‘` 是 U+2018，手打成 `'` 就找不到目录。
6. **表情缓存是加密的**：`business\emoticon\Persist` 下 287 个文件全部是 16 字节对齐的 AES 密文，文件名是 md5，没有扩展名，拷出来不是 gif。
7. **收集表情依赖 CDN 开关**：`wechat.media.allowStickerCdn` 目前是 `false`，池子里已有 5 条 `attempts: 3` 的失败记录，与此吻合。

## 5. 配置要点

- `runtime.sender = wechat-hook`，`hook.expectedVersion = 4.1.10.27`，`hook.baseUrl = http://127.0.0.1:30001`
- `ports`：weflow 5031 / onebot 11229 / adapter 8766 / dshPlugin 11230
- `media.allowStickerCdn = false`（待开）
- `stickers.collectEnabled = true`，`stickers.enabled = true`
- `whitelist.private = []`、`whitelist.groups = []`（尚未绑定任何聊天）

## 6. 下一步

1. 在 DSH 里安装本机插件 `D:\zlh‘s program\data\workspace\packages\dsh-social-bridge-plugin`，启用后从托盘完整退出并重开 DSH。
2. 回到 WeChatAgent 点「启动服务」，确认 11230 端口起来。
3. 绑定允许的聊天（主号 / 目标群），再考虑表情与人格。

详细需求清单见 [ISSUES.md](ISSUES.md)。
