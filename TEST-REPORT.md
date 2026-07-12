# 测试报告

版本：0.1.0

测试日期：2026-07-11

补充验证日期：2026-07-12

## 已执行

- Python 3.13 环境下完成全部脚本 AST 解析与 `compileall`。
- 使用包含两个章节和两张图片的 Markdown 初始化测试项目。
- 验证图片复制、缺失素材检查、事实核验字段、隐私审核字段和分镜引用。
- 使用缓存场景音频测试 TTS 复用、场景停顿、拼接和响度处理。
- 生成 SRT、ASS 与 JSON 字幕。
- 验证中英混合字幕中的 `Activate Card` 不会在英文单词中间断开。
- 合并配音时间、字幕、图片、标注和隐私遮挡为确定性时间线。
- 验证 HTTP Range 请求和两类审核结果写入接口。
- 使用 Playwright 和 Chromium 按时间点逐帧渲染。
- 使用 FFmpeg 合成 H.264 与 AAC MP4。
- 使用 ffprobe 检查分辨率、时长、视频轨和音频轨。
- 对每个场景抽取关键帧并生成 contact sheet。
- 执行黑帧和长静音检测。

## 测试结果

离线流程通过。测试成片包含图片缩放、按钮圈选、字幕和实心隐私遮挡。

## 尚需用户环境验证

- ElevenLabs、OpenAI 和 Azure Speech 的真实请求需要对应 API Key。
- 各提供商的普通话自然度、音色授权、计费和并发限制需要按用户账户实际验证。
- 银行事实核验依赖制作时打开的官方页面，不能用示例来源直接发布。
- 最终发布前仍需人工检查每张关键帧中的隐私遮挡和页面时效。

## Public repository checks

The public repository package also includes automated checks for:

- Python 3.11 and 3.12 source compilation.
- Markdown parsing and image reference handling.
- Configuration deep merge and aspect-ratio parsing.
- Project path traversal rejection.
- Project initialization and local asset copying.
- Codex Skill metadata validation.
- Render-time fact, privacy, input, and human-approval guards.
- Review-page HTML escaping checks.
- Self-contained example asset and contract validation.
- JSON parsing and SVG XML validation.

These checks run without paid TTS requests and without uploading tutorial assets.
