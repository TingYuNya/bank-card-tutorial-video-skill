# Architecture

## 设计目标

项目将视频制作拆成可检查、可恢复、可重复执行的阶段。每个阶段都有明确输入、输出和校验条件，避免将全部判断压在一次生成中。

## 数据流

```text
Markdown + 本地图片
        ↓
项目初始化与素材清单
        ↓
事实核验 + 隐私审核 + 文稿整理
        ↓
配音稿 + 屏幕文案 + 分镜数据
        ↓
分镜审核页
        ↓
分场景 TTS + 字幕对齐
        ↓
时间线数据 + 时间线预览
        ↓
固定画布逐帧渲染
        ↓
FFmpeg 编码
        ↓
ffprobe + 抽帧 + contact sheet 验收
```

## 主要组件

### 初始化层

`scripts/init_project.py` 解析 Markdown、复制本地图片、生成章节和素材清单。远程图片不会自动下载，保证项目能够在本地复现。

### 内容层

内容层由 Agent 按 `SKILL.md` 和 `references/` 中的数据契约生成结构化文件。事实核验、隐私审核和分镜必须保留可追踪编号。

### 配音与字幕层

`scripts/generate_tts.py` 按场景生成音频，并依据文本、声音和参数计算缓存键。`scripts/build_subtitles.py` 将字符级或词级时间映射为 SRT、ASS 和 JSON。

### 审核层

`templates/storyboard-audit.html` 用于逐场景审核。`templates/timeline-preview.html` 将音频、字幕、图片和镜头动作放入同一条时间线。

预览服务由 `scripts/serve_preview.py` 提供，并支持 HTTP Range，保证音视频可随机跳转。

### 渲染层

`templates/final-player.html` 暴露确定性的时间定位接口。`scripts/render_final_video.py` 使用 Playwright 在固定逻辑画布中恢复任意时间点，再逐帧截图并交给 FFmpeg 编码。

### 验收层

`scripts/quality_check.py` 检查媒体信息、黑帧、静音和场景关键帧，同时生成 contact sheet 和质量报告。

## 真相源优先级

内容判断建议遵循：

```text
银行官方协议与费率表
    > 银行官网和官方帮助中心
    > 卡组织与监管机构资料
    > 官方应用页面
    > 用户草稿
```

画面判断建议遵循：

```text
用户原始截图或录屏
    > 已确认的分镜数据
    > 自动生成的信息卡
```

## 固定画布

预览与最终导出使用相同逻辑画布。高清输出通过 DPR 或编码参数完成，避免响应式布局在导出时改变元素尺寸和位置。

## 可恢复执行

运行产物按阶段写入 `work/`、`audio/`、`subtitles/`、`review/`、`renders/` 和 `quality/`。修改单个场景后，可以复用未变化的配音、字幕和素材。
