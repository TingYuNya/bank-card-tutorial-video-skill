---
name: bank-card-tutorial-video:教程成片
description: 将包含正文与图片的 Markdown 银行卡开卡教程，处理为经过事实核验、隐私检查、配音、字幕、分镜审核、时间线预览和最终验收的 MP4 成片。适用于银行卡开卡、激活、绑卡、还款、账单与账户设置教程。触发词：银行卡教程成片、开卡视频教程、Markdown做视频、图文教程配音、银行卡教程剪辑
---

# 银行卡教程成片

## 目标

输入一份 Markdown 文档及其引用图片，输出：

- 经过逻辑整理和事实核验的图文教程。
- 适合真人感配音的口语稿。
- 屏幕短文案与章节标题。
- 可审核的分镜页面。
- 可拖动、可倍速播放的时间线预览。
- 带字幕、图片、标注、隐私遮挡和配音的最终 MP4。
- 字幕、配音、分镜、事实核验和验收报告等中间产物。

本 Skill 采用“文档分析、事实核验、分镜审核、时间线预览、最终渲染、抽帧验收”的工作流。流程设计参考 `chengfeng-videocut-skills` 的审核页、时间线预览、固定画布和逐帧渲染思路，并针对纯 Markdown、图片素材和 AI 配音场景重构。

## 强制原则

1. 金融产品信息可能随时间、地区、申请渠道和账户状态变化。所有费率、资格、押金、信用额度、年费、外汇手续费、还款、退款、信用报告、卡组织权益等陈述必须核验。
2. 默认只使用银行官网、卡组织官网、监管机构、产品协议、费率表、帮助中心和官方应用说明。默认不使用中文资讯站、聚合站、自媒体和论坛。
3. 用户未允许使用中文官方页面时，优先使用英文官方来源。某项信息只存在于银行官方中文页面时，先标记为待授权来源。
4. 不依据记忆补写当前费率、当前资格或当前操作入口。
5. 图片中的卡号、CVV、有效期、验证码、账户号、详细地址、邮箱、手机号、二维码、条形码、客户编号、余额和交易记录必须逐张检查。
6. 隐私检查没有完成时禁止最终渲染。
7. 高风险事实未解决时禁止最终渲染。可以删除该陈述、改成有条件表述，或在画面中明确显示核验边界。
8. 分镜和时间线预览使用同一套固定画布。最终渲染只能读取已经确认的时间线。
9. 导出成功后必须使用 `ffprobe` 检查，并对每个场景至少抽取一张关键帧。
10. 用户提供了现有口吻、选项、断句规则、UI 风格或素材组织方式时，完整保留。除非用户明确要求删除，不擅自精简既有功能。

## 推荐项目输入

```text
input/
├── tutorial.md
└── images/
    ├── 01-login.png
    ├── 02-activate.png
    └── 03-payment.png
```

Markdown 示例：

```markdown
# Capital One 押金卡激活与还款教程

## 激活卡片

登录应用后，进入对应卡片页面，点击 Activate Card。

![激活入口](images/02-activate.png)

## 添加还款账户

在 Payments 页面添加银行账户，并核对 routing number 和 account number。

![还款账户](images/03-payment.png)
```

## 输出结构

```text
project/
├── source/
│   ├── tutorial.original.md
│   └── assets/
├── work/
│   ├── sections.json
│   ├── manifest.json
│   ├── fact-check.json
│   ├── privacy-review.json
│   ├── revised-article.md
│   ├── narration.json
│   ├── on-screen-text.md
│   ├── storyboard.json
│   ├── audio-timeline.json
│   ├── subtitles.json
│   └── timeline.json
├── audio/
│   ├── scenes/
│   ├── narration.wav
│   └── timings.json
├── subtitles/
│   ├── subtitles.srt
│   └── subtitles.ass
├── review/
│   ├── storyboard-audit.html
│   └── timeline-preview.html
├── renders/
│   ├── final-player.html
│   ├── frames/
│   └── 银行卡教程-final.mp4
├── quality/
│   ├── frames/
│   ├── contact-sheet.jpg
│   └── quality-report.md
└── sources/
    └── source-list.md
```

## 第 0 步：读取配置和项目规则

先读取：

```text
config/default.json
```

如果项目目录包含以下文件，也要先读：

```text
AGENTS.md
README.md
project.json
```

配置只保存明确的用户选择，例如比例、配音提供商、字体、字幕安全区、是否启用背景音乐、审核模式和输出质量。事实核验结果、分镜决策和隐私坐标应写入项目的 `work/`，不要写入全局配置。

## 第 1 步：初始化项目

运行：

```bash
python scripts/init_project.py \
  --input /absolute/path/to/tutorial.md \
  --project /absolute/path/to/project
```

该脚本会：

- 复制原始 Markdown。
- 解析标题、段落、列表和图片引用。
- 复制本地图片到 `source/assets/`。
- 生成 `work/sections.json` 和 `work/manifest.json`。
- 生成事实核验、隐私检查、配音稿和分镜的空白模板。

初始化后先检查缺失图片：

```bash
python scripts/validate_project.py \
  --project /absolute/path/to/project \
  --phase initialized
```

## 第 2 步：文档诊断与事实核验

### 2.1 先拆出所有可核验陈述

将每项陈述写入 `work/fact-check.json`：

```json
{
  "id": "claim-001",
  "claim": "该卡没有年费",
  "category": "fee",
  "region": "US",
  "status": "verified",
  "severity": "high",
  "source_title": "官方费率表",
  "source_url": "https://example.com/official",
  "source_type": "product_agreement",
  "source_official": true,
  "source_language": "en-US",
  "checked_at": "2026-07-11",
  "effective_date": null,
  "notes": "费率表列明 annual fee 为 0 美元"
}
```

`status` 只允许：

```text
verified
qualified
removed
unresolved
```

`severity` 只允许：

```text
high
medium
low
```

以下内容通常属于高风险陈述：

- 申请资格和身份证明要求。
- 押金金额与退还条件。
- 年费、外汇手续费、取现费、逾期费和利率。
- 信用额度提高、毕业转卡和信用报告。
- 还款到账时间、提前还款、自动还款和可用额度恢复。
- 开卡奖励、返现、保险和卡组织权益。
- 是否支持特定支付平台、地区或账单地址。

### 2.2 检查教程完整性

银行卡开卡教程至少检查以下环节是否需要出现：

- 产品适用地区与申请条件。
- 开卡前准备材料。
- 申请入口与账户注册。
- 身份核验和地址要求。
- 押金或首笔入金。
- 审批与寄送。
- 收卡激活。
- 设置 PIN、电子账单和通知。
- 添加还款账户。
- 首次消费与还款。
- 失败页面和常见错误。
- 隐私提示和风险边界。

并非每张卡都需要全部环节。删除不适用内容，保留适用项的官方依据。

### 2.3 输出三套文稿

写入：

```text
work/revised-article.md
work/narration.json
work/on-screen-text.md
sources/source-list.md
```

`narration.json` 结构：

```json
{
  "title": "教程标题",
  "language": "zh-CN",
  "scenes": [
    {
      "id": "scene-001",
      "section_id": "section-001",
      "text": "登录账户后，点击需要激活的信用卡。",
      "pause_after": 0.25,
      "pronunciations": {
        "Capital One": "Capital One"
      }
    }
  ]
}
```

配音稿规则：

- 逐句口语化，保留信息密度。
- 英文按钮名和产品名保持官方拼写。
- 数字、日期、利率、费用和账户字段写成容易正确朗读的形式。
- 不朗读 URL、引用编号、素材路径和内部备注。
- 每个场景只承担一个步骤、一个证据或一个注意事项。
- 相邻场景之间保持自然承接。
- 不添加文档和官方资料均未支持的结论。

## 第 3 步：逐张隐私检查

写入：

```text
work/privacy-review.json
```

结构：

```json
{
  "assets": [
    {
      "asset": "source/assets/02-activate.png",
      "reviewed": true,
      "contains_sensitive_data": true,
      "notes": "卡号与姓名需要遮挡",
      "redactions": [
        {
          "x": 0.12,
          "y": 0.18,
          "w": 0.54,
          "h": 0.08,
          "label": "card_number"
        }
      ]
    }
  ]
}
```

坐标采用相对于原图的 0 到 1 归一化坐标。

默认需要遮挡：

- 完整卡号，只保留必要的后四位。
- CVV、有效期和 PIN。
- 一次性验证码和登录验证码。
- Routing number、account number、IBAN 和账户号。
- 姓名、详细地址、邮箱、手机号和生日。
- 身份证件、税号和客户编号。
- 二维码、条形码和可复用登录链接。
- 真实余额、信用额度和交易记录，除非教程确实需要且用户明确同意展示。

遮挡使用实心遮挡作为默认方式。模糊效果只能用于低风险信息。

## 第 4 步：生成分镜

写入：

```text
work/storyboard.json
```

每个分镜至少包含：

- 关联的配音场景 ID。
- 完整配音文本。
- 画面任务。
- 主视觉类型。
- 主素材。
- 聚焦区域。
- 支撑该画面的 `source_claim_ids`。纯章节标题可以填写 `fact_check_exempt_reason`。
- 镜头动作。
- 屏幕短文案。
- 圈选、箭头和标签。
- 隐私遮挡。
- 事实来源和核验状态。

示例：

```json
{
  "version": 1,
  "scenes": [
    {
      "id": "visual-001",
      "narration_scene_id": "scene-001",
      "kind": "image",
      "asset": "source/assets/02-activate.png",
      "task": "展示激活入口",
      "motion": {
        "type": "focus",
        "start_scale": 1.0,
        "end_scale": 1.18,
        "focus_x": 0.72,
        "focus_y": 0.36
      },
      "screen_text": "选择 Activate Card",
      "overlays": [
        {
          "type": "rect",
          "x": 0.58,
          "y": 0.29,
          "w": 0.30,
          "h": 0.12,
          "label": "Activate Card"
        }
      ],
      "redactions": [],
      "source_claim_ids": ["claim-003"]
    }
  ]
}
```

画面选择规则：

- 操作步骤优先使用用户原始截图或录屏。
- 讲页面按钮时，主视觉保持原图，动画仅用于裁切、放大、圈选和箭头。
- 同一张图重复使用时，每次承担不同任务，例如全貌、局部入口、结果确认。
- 缺少图片时，可以用简洁步骤卡、流程图或风险提示卡补足。
- 屏幕短文案控制在一到两行。
- 一页只讲一个动作或一个结论。
- 画面中不显示素材路径、内部状态、事实核验备注和实现说明。
- 原始截图中的银行品牌 UI 不要被重画成相似界面，以免造成误导。

## 第 5 步：生成分镜审核页

运行：

```bash
python scripts/build_review_pages.py \
  --project /absolute/path/to/project
```

启动审核服务：

```bash
python scripts/serve_preview.py \
  --project /absolute/path/to/project \
  --port 8767
```

打开：

```text
http://127.0.0.1:8767/review/storyboard-audit.html
```

审核页需要检查：

- 每句配音是否匹配当前画面。
- 图片是否用错。
- 标注位置是否准确。
- 图片是否有未遮挡隐私。
- 事实来源是否与场景对应。
- 画面是否过度拥挤。
- 相邻场景是否重复。

默认审核模式为 `user`。用户明确选择 `auto` 时，Agent 仍需完成一次自审，并写入 `work/storyboard-review.json`。

## 第 6 步：生成真人感配音

支持：

```text
elevenlabs
openai
azure
```

运行：

```bash
python scripts/generate_tts.py \
  --project /absolute/path/to/project \
  --provider elevenlabs
```

配音按场景分别生成，然后合并。这样可以：

- 单独重做某一句。
- 保持场景时间边界稳定。
- 精确控制停顿。
- 把字幕和画面绑定到同一场景。

配音参数从 `config/default.json` 和环境变量读取。

建议的普通话讲解风格：

```text
语速接近日常讲解
停顿清晰
语气平静
不使用新闻播报腔
不使用广告推销腔
英文按钮名读音清楚
数字和费用读法准确
```

OpenAI 配音需要在最终视频说明中标注 AI 生成语音。其他提供商也应遵循其适用的披露要求。

## 第 7 步：生成字幕

运行：

```bash
python scripts/build_subtitles.py \
  --project /absolute/path/to/project
```

输出：

```text
subtitles/subtitles.srt
subtitles/subtitles.ass
work/subtitles.json
```

字幕规则：

- 默认每行最多 16 个中文字符，英文单词按整体计算。
- 最多两行。
- 按语义和标点切分。
- 英文按钮名、卡名、金额和日期不在中间拆开。
- 单条字幕尽量保持 1.0 到 6.0 秒。
- 字幕与 TTS 时间戳对齐。
- 提供商没有原生时间戳时，优先用 OpenAI `whisper-1` 生成词级时间；没有可用对齐服务时才按字符权重估算。

## 第 8 步：生成时间线

运行：

```bash
python scripts/build_timeline.py \
  --project /absolute/path/to/project
```

该脚本会把配音时长、字幕、图片、镜头动作、遮挡、标注和屏幕短文案合并到：

```text
work/timeline.json
```

时间线中的每个动作必须由明确时间或场景进度驱动。不要依赖浏览器自然播放时间、CSS 自动动画累计或不可复现的随机效果。

## 第 9 步：时间线预览

打开：

```text
http://127.0.0.1:8767/review/timeline-preview.html
```

时间线预览必须支持：

- 播放和暂停。
- 可拖动进度条。
- 音量。
- 1 倍、1.25 倍、1.5 倍和 2 倍速度。
- 当前场景信息。
- 与最终播放器完全一致的画布。

预览检查：

- 画面切换是否贴合语义。
- 图片停留时间是否足够。
- 放大区域是否准确。
- 标注有没有挡住按钮或字幕。
- 字幕是否过长或跳动过快。
- 隐私遮挡是否覆盖完整。
- 章节之间是否需要短停顿。
- 配音是否存在错读、机械停顿或音色不连续。

时间线确认结果写入：

```text
work/timeline-review.json
```

## 第 10 步：最终渲染

渲染前执行：

```bash
python scripts/validate_project.py \
  --project /absolute/path/to/project \
  --phase render
```

通过后运行：

```bash
python scripts/render_final_video.py \
  --project /absolute/path/to/project
```

渲染流程：

1. 浏览器按固定逻辑画布加载 `renders/final-player.html`。
2. 对每一帧调用 `window.seekTo(time)`。
3. 将固定画布截图为 PNG。
4. FFmpeg 将图片序列编码为 H.264。
5. 合并配音和可选背景音乐。
6. 输出最终 MP4。

默认质量：

```text
H.264
30 fps
CRF 14
preset slow
yuv420p
AAC 192 kbps
```

临时预览可以改成 JPEG、CRF 18 和 `preset medium`。正式交付继续使用 PNG 中间帧。

## 第 11 步：验收

运行：

```bash
python scripts/quality_check.py \
  --project /absolute/path/to/project
```

验收包括：

- `ffprobe` 检查分辨率、帧率、时长、编码和音频。
- 对每个场景抽取中间关键帧。
- 生成 contact sheet。
- 检查黑帧和长静音。
- 检查字幕安全区。
- 检查所有隐私遮挡在最终视频里仍然有效。
- 检查最终画面与时间线预览在同一时间点一致。

完成标准：

```text
final.mp4 存在且可播放
分辨率与配置一致
帧率与配置一致
存在音频轨道
时长与 narration.wav 基本一致
所有场景有关键帧
没有 unresolved 高风险事实
所有图片 privacy reviewed = true
分镜和时间线已确认
```

## 最终交付

至少交付：

```text
renders/银行卡教程-final.mp4
work/revised-article.md
work/narration.json
work/fact-check.json
sources/source-list.md
subtitles/subtitles.srt
subtitles/subtitles.ass
audio/narration.wav
work/storyboard.json
work/timeline.json
quality/quality-report.md
```

## 错误处理

- 缺少图片：列出缺失路径并停止。
- 官方资料冲突：保留各方来源，标明地区、日期和适用条件，不自行裁定。
- 页面 UI 与官方说明不一致：优先把教程表述写成“以账户当前页面为准”，并保留截图日期。
- TTS 错读：只重做对应场景，保持其他场景文件和时间线不变。
- 字幕对齐误差：优先重新生成该场景时间戳，不重做整条视频。
- 预览正常、导出变小：检查逻辑画布、DPR、CSS 最大尺寸和 `window.seekTo` 的固定状态。
- 最终遮挡偏移：检查遮挡坐标是否相对于原图，检查图片 `object-fit` 后的实际显示框。

## 边界

适合：

- 银行卡开卡、激活、绑卡、还款和账户设置教程。
- 以 Markdown、截图和少量录屏为主的教程。
- 中文配音与中英混合按钮名。
- 需要事实核验、隐私检查和可审计中间产物的教程。

暂不优先处理：

- 多机位真人拍摄。
- 需要剪辑软件工程文件的复杂调色和多轨混音。
- 模仿特定真人声音。
- 自动绕过银行风控、身份验证或地区限制。
- 使用伪造页面、伪造审批结果或伪造账户余额制作教程。
