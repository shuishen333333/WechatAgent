# 需求与改造清单

> 来源：2026-10-25 用户口述（编号沿用用户原话，第 7 条未提及）。
> 每条给出：现状证据 / 初步方案 / 改动面。**都还没动手**，等确认优先级。
>
> **2026-10-26 更新**：第 1 条（禁用/启用不丢配置）**取消，不做**。第 3 条已定位到确切报错
> `IMAGE_STICKER_LOCAL_COPY_UNAVAILABLE`，是配置开关问题、不用改代码。其余保留。

## 1. ~~好友与群聊要能随时"禁用/启用"，且不丢配置~~ —— 2026-10-26 取消

> 用户确认不再需要此功能，本节仅留档。

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

**2026-10-26 已定位（不用改代码）**：服务已跑起来，白名单里有 2 个好友 + 2 个群，好友确实在发表情，
但池子 `entries: 0`、`pending: 12`。`state/logs/reader.stderr.log` 里每条都是：

```
Image resolution failed: IMAGE_STICKER_LOCAL_COPY_UNAVAILABLE exceptionType=RuntimeError
```

含义：本机缓存是加密的、拿不到可校验的明文，必须回退到"从腾讯 CDN 下载"，而
`wechat.media.allowStickerCdn = false`，于是每次都在这里断掉，重试 3 次后进 `pending` 等死。

**解法**：设置 → 图片与表情包 → 勾选「允许从腾讯下载缺失的表情包」→ 保存 → 重启服务。

## 4. 发原图 / 以文件发送，仍然拿不到原图

**2026-10-26 实测（已修一半）**：

1. 用真实消息验证，`GET /api/v1/images/<id>` 返回的是 **117×210 / 6.7 KB**，就是微信的缩略图。
2. 查消息 XML 原文：`cdnthumbwidth=117 cdnthumbheight=210`、`cdnhdwidth=0 cdnhdheight=0`、`length=61800`。
   也就是说**对方那条消息本身就没有高清版**，本机也只缓存了缩略图——磁盘上根本不存在
   `cc82c877…`（61.8 KB 那张）的任何文件，全盘搜不到。
3. 所以"点原图、发文件都拿不到"有两层原因：
   - 图片通道：微信 4.x 桌面端**不会替你下载**聊天图片，只有你在电脑微信里点开那张图才会把
     `.dat`（压缩图）/`_h.dat`（原图）落盘；仓库 `docs/IMAGE_INPUT.md` 也是这么写的。
   - 文件通道：`social-engine.js:143` 在闲聊模式下**直接丢弃带 files 的消息**
     （`file_ignored_in_social_mode`），所以"以文件发送"根本没进模型。

**已改**：`scripts/resolve-wechat-image.py`
- 解析顺序改为 `_h.dat` → `.dat` → `_t.dat`，并且**取所有候选里像素面积最大的那份**，
  不再"先到先得"；
- 只剩缩略图（最长边 < 256）时抛 `IMAGE_ONLY_THUMBNAIL`，不再把 117×210 的图当原图喂给模型，
  机器人可以如实说"只拿到缩略图"。

**还差**：
- 图片通道要拿真原图，只能靠微信自己下载（在机器人那个微信窗口点开一次），或者逆微信 4.x 的
  CDN 协议直连下载（`cdnmidimgurl` 是二进制块不是 URL，风险高，暂不做）。

**2026-10-26 追加：文件通道已打通**
- `reader-api.py`：文件消息若是图片（jpg/jpeg/png/gif/webp/bmp，≤20 MB），在 `poll()` 里
  注册成一个 image（`kind: 'file-image'`），载荷改写成普通图片事件，于是复用整条图片管线，
  不需要动适配器和社交引擎；
- `resolve-wechat-image.py`：`kind == 'file-image'` 时直接去 `msg/file` 与
  `FileStorage/File` 里按 **文件名 + 大小 + md5** 校验后读取原始文件，不经过任何加密缓存；
- 实测：`IMG_5940.JPG`（452 KB）解析为 **720×1280**，而同一台机器上图片通道只有 117×210 的缩略图；
- 文件没下载时抛 `IMAGE_FILE_NOT_DOWNLOADED`（"电脑微信尚无可验证的完整文件"）。



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
