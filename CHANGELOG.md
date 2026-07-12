# Changelog

本项目遵循语义化版本的基本规则。当前仍处于早期版本，数据契约和命令行参数可能在后续版本中扩展。

## Unreleased

1. 修复 Codex Skill 名称格式，使官方校验器可以正常识别。
2. 渲染前强制执行事实核验、隐私检查、输入文件和人工审批验证。
3. 对审核页面的动态内容进行 HTML 转义，降低本地内容注入风险。
4. 补充可直接运行的虚构示例素材，并统一示例契约中的路径。
5. 增加 Skill 元数据、审核安全、渲染守卫和完整示例内容的自动化测试。

## 0.1.0 · 2026-07-11

首次公开版本。

1. 支持 Markdown 与本地图片初始化。
2. 增加事实核验和隐私检查契约。
3. 支持 ElevenLabs、OpenAI 和 Azure Speech 配音。
4. 生成 SRT、ASS 和 JSON 字幕。
5. 提供分镜审核页和时间线预览页。
6. 支持 Playwright 逐帧渲染和 FFmpeg 合成。
7. 增加 ffprobe、逐场景抽帧、contact sheet、黑帧和静音检查。
8. 增加许可证说明、安全策略、行为准则、支持范围、金融免责声明和 GitHub 协作模板。
9. 增加 GitHub Actions、Python 3.11/3.12 单元测试和静态资源校验。
10. README 增加真实输出帧、contact sheet、配音提供商对照和发布说明。
11. 增加 `ROADMAP.md`、`CITATION.cff` 和 `CODEOWNERS`。
12. 增加可重复执行的发布打包脚本和标签构建工作流。
