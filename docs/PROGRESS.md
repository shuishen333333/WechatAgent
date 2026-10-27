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
- [x] DSH 桥接插件安装并启用（端口 `11230` 在监听）
- [x] 启动服务（2026-10-26 10:24，30001 / 11230 / 8766 / 11229 / 5031 全部在监听）
- [x] 绑定允许的聊天：私聊 `447040987`、`1306012985`，群 `321691740`、`901039569`
- [ ] 表情自动收集（收到 12 张、入池 0 张，见 ISSUES #3，需开 `allowStickerCdn`）

## 4. 已知坑（踩过的）

1. **「自动查找账号」永远找不到**：它只扫 `Documents`、家目录、OneDrive 和注册表 `FileSavePath`，**不扫 D 盘**。必须手动「选择文件夹」。
2. **多账号时路径被清空**：选 `xwechat_files` 会识别出 2 个账号，界面随后把路径清空；再点「识别此目录」就退化成自动扫描 → 报"未找到"。正解是**直接选到 `wxid_xxx` 这一层**。
3. **抓密钥必须在"未登录"状态**：密钥只在登录那一刻派生，先登录好再点连接必然 `READER_SETUP_TIMEOUT`。顺序：退出登录 → 点连接 → 立刻扫码。
4. **版本必须 4.1.10.27**：hook 与 native 组件都按这个版本编译，本机 4.1.15.56 会被判 `HOOK_VERSION_MISMATCH`。
5. **路径里有弯引号**：`D:\zlh‘s program\` 中 `‘` 是 U+2018，手打成 `'` 就找不到目录。
6. **表情缓存是加密的**：`business\emoticon\Persist` 下 287 个文件全部是 16 字节对齐的 AES 密文，文件名是 md5，没有扩展名，拷出来不是 gif。
7. **收集表情依赖 CDN 开关**：`wechat.media.allowStickerCdn` 目前是 `false`，池子里已有 5 条 `attempts: 3` 的失败记录，与此吻合。
8. **改脚本要同时改"安装目录"和"运行目录"**（2026-10-26 踩坑）：程序启动时会把
   `app\resources\project\*` **覆盖**到 `data\workspace\*`。只改运行目录的话，下一次
   启动（甚至只是重启服务）就被原版覆盖回去，表现为"补丁突然失效"。正确做法：
   两边一起改，改完再重启服务。本次回滚就发生在 19:47（两个脚本 mtime 同时变成原版大小）。
9. **程序更新/修复安装会把 `app\resources` 整包换掉**（2026-10-27 复现）：
   `app\resources\{project,runtime,vendor}` 目录时间变成更新时间，补丁文件全部回到发布版，
   运行目录随后被同步覆盖。恢复：仓库里执行 `pwsh -File scripts\apply-local-patches.ps1`，
   再重启服务。**每次更新后都要跑一次。**

## 5. 配置要点

- `runtime.sender = wechat-hook`，`hook.expectedVersion = 4.1.10.27`，`hook.baseUrl = http://127.0.0.1:30001`
- `ports`：weflow 5031 / onebot 11229 / adapter 8766 / dshPlugin 11230
- `media.allowStickerCdn = true`（已开，表情收集正常）
- `stickers.collectEnabled = true`，`stickers.enabled = true`
- `whitelist.private = [447040987, 1306012985]`、`whitelist.groups = [321691740, 901039569]`

## 6. 下一步

1. 需求 #2 中文化（能力与权限页英文文案）。
2. 需求 #6 好友备注。
3. 需求 #5 聊天改人格（最重，需审计与回滚）。

详细需求清单见 [ISSUES.md](ISSUES.md)。
