# 产物契约

## 固定画布

最终播放器、时间线预览和逐帧渲染必须使用同一套逻辑画布。画布尺寸来自 `config/default.json` 的 `aspectRatio` 与 `canvas` 映射。

- HTML 内部按逻辑画布布局。
- 高清输出通过 Playwright `device_scale_factor` 提高像素尺寸。
- 不把 CSS 逻辑尺寸直接改成高清输出尺寸。
- 最终画面禁止滚动。
- 每个时间点必须能够通过 `window.seekTo(time)` 独立恢复。

## 时间线

`work/timeline.json` 必须包含：

```json
{
  "canvas": {"width": 1920, "height": 1080, "dpr": 1},
  "fps": 30,
  "total_duration": 60,
  "audio": "audio/narration.wav",
  "scenes": [],
  "subtitles": []
}
```

场景时间不得重叠。允许场景之间存在不超过 50 毫秒的浮点误差。

## 最终播放器

`renders/final-player.html` 必须暴露：

```js
window.seekTo = async function seekTo(time) {
  return { scene, kind, time };
};

window.finalVideo = { scenes, totalDuration };
```

渲染期间：

- 不依赖 `requestAnimationFrame` 推进动画。
- 不依赖 CSS animation 的自然时间。
- 所有缩放、移动、显隐、视频 seek 和字幕显示均由传入时间决定。
- 图片、视频、遮挡和标注放在同一变换组中，避免缩放后坐标错位。

## 图片坐标

`overlays` 与 `redactions` 使用相对于原图的归一化坐标：

```text
x, y, w, h ∈ [0, 1]
```

播放器先计算 `object-fit: contain` 后的真实图片显示框，再在图片组内部应用坐标。

## 审核产物

分镜审核：

```text
work/storyboard-review.json
```

时间线审核：

```text
work/timeline-review.json
```

至少包含：

```json
{
  "approved": true,
  "approved_by": "user",
  "notes": "",
  "saved_at": "ISO-8601"
}
```

## 最终验收

- 每个场景至少抽取一张最终视频关键帧。
- 对照预览和最终帧的相同时间点。
- 自动检查不能替代隐私人工复核。
