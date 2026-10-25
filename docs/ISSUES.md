# 需求与改造清单

> 来源：2026-10-25 用户口述（编号沿用用户原话，第 7 条未提及）。
> 每条给出：现状证据 / 初步方案 / 改动面。**都还没动手**，等确认优先级。

## 1. 好友与群聊要能随时"禁用/启用"，且不丢配置

**现状**：唯一开关是 `wechat.whitelist.private` / `wechat.whitelist.groups`（数组）。
移除即等于"这个聊天不存在"，UI 里看不到，重新加入后要重新配一遍（人格、技能、回复模式、表情、上下文等都以 `private:wxid` / `group:id` 为 key 存在 `chatModes`、`dshAccess`、`stickers.chats`、`context.chats`、`proactive.chats`、`persona.chats`、`memberMemory.chats` 等字典里）。

**初步方案**：把"允许"与"启用"拆成两件事——
- 白名单继续表示"允许管理"，新增 `disabled: true` 标记（或 `enabled` 集合）；
- 服务端在装配会话时过滤 `disabled`（不读消息、不回复、不主动、不收集），但配置原样保留；
- UI：会话列表加一个总开关，禁用态灰显。

**改动面**：`config` schema → `console-server.mjs` 校验 → `social-bridge.js` 装配 → `public/console/*` 列表与开关。中等。

## 2. 能力/权限页大量英文简介，需要中文化

**现状**：`能力`、`权限`、插件工具描述里有成段英文。多数是**给模型看的 prompt 片段**（tool description / skill description），部分是给人看的 UI 文案。

**注意**：如果直接翻译 "给模型看的" 那段，会改变模型行为（模型对这些描述很敏感）。建议拆两层：
- UI 文案：中文化，纯展示；
- 模型 prompt：保留英文原文，另加一行中文摘要（或做 `locale` 字段，渲染时取当前语言）。

**改动面**：`public/console/*` + 插件 `*.mjs` 里的 description 字符串。小到中等，但需要逐条确认哪段是喂模型的。

## 3. 表情包从另一个号（主号）导入

**现状**：微信 4.x 把收藏表情加密了。主号目录 `business\emoticon\Persist` 下 287 个文件，**100% 是 16 字节对齐的 AES 密文**，文件名是 md5、无扩展名；`Thumb` 331 个同理。老版本（3.9）的 `FileStorage\CustomEmotion\*.gif` 明文路径在 4.x 已不存在。

三条路：
- **A 收进来（推荐）**：开 `wechat.media.allowStickerCdn`，把主号加入允许范围，主号逐条发表情 → 后台按 md5 从 CDN 下载 → 校验 → 入池。上限 50 张。
- **B 手机导出**：`我 → 表情 → 我的表情 → 保存到相册`，传到电脑后「添加表情包」（一次 ≤20 张，文件名即默认描述）。
- **C 离线解密（研究性）**：把主号登进 4.1.10.27 抓一次库密钥 → 用 `nt_decrypt` 解 `db_storage\emoticon\emoticon.db` 拿每条表情的 aeskey → AES-CBC 解密 `Persist`。可行性未验证（收藏表情的 aeskey 是否就存在该库里）。

**现状缺陷**：池子里已有 5 条 `attempts: 3` 的失败记录，疑似就是 `allowStickerCdn=false` 导致。

## 4. 发原图 / 以文件发送，仍然拿不到原图

**证据**：`scripts/resolve-wechat-image.py:89`

```python
for suffix in ('.dat', '_h.dat', '_t.dat'):
```

解析顺序是 **`.dat`（压缩图）优先**，`_h.dat`（高清）排第二，`_t.dat`（缩略图）兜底。也就是说只要 `.dat` 存在，就永远拿不到 `_h.dat`。

**初步方案**：
- 优先 `_h.dat`，再回退 `.dat` / `_t.dat`；
- 或按消息里的 `hd`/`cdnbig` 标记与文件体积判断；
- "以文件形式发送"的图片走的是 `msg/file` 路径而不是 image 通道，需要在媒体解析里补一条 file→image 的分支。

**改动面**：`resolve-wechat-image.py` + `wechat_media.py`（+ 可能 `image-input.mjs`）。小。

## 5. 聊天反馈：能在聊天里修改自己的人格

**现状**：人格只能从「人格」页改，聊天里没有写入口。

**初步方案**：给模型一个受控工具 `persona_patch`（或 `persona_update`）：
- 只允许改**当前聊天绑定**的那张人格卡；
- 仅支持"追加/替换某个段落"，不做全文重写；
- 每次修改写审计日志 + 生成旧版本快照，可在 UI 一键回滚；
- 需要显式开启（默认关），并限制单次字节数与频率。

**风险**：自我修改容易跑偏、也容易被聊天内容注入带歪。必须默认关闭 + 可回滚。

**改动面**：插件工具 + 人格存储版本化 + UI。中大。

## 6. 每个好友一个备注，用来描述他的特质

**现状**：已有「群友记忆」（`member-memory.mjs` / `member-memory-policy.mjs`），按**群成员**记录；私聊没有等价物，也没有"全局好友备注"。

**初步方案**：
- 把 member-memory 的 key 扩展到私聊 `wxid`；
- 新增"好友备注"字段（自由文本，几百字），注入到该聊天的上下文；
- UI 放在「聊天」详情页。

**改动面**：`member-memory*.mjs` + 配置 schema + UI。中等。

## 8. 用 git 保存进度并推到 GitHub

已在本目录初始化仓库（基线 = 上游 `sourcepro5/WeChatAgent` v0.4.0），本文件与 `PROGRESS.md` 是第一批本地改动。推送需要一个 GitHub 仓库地址与凭据（用户提供）。

> 附：第 7 条用户未提，留空。
