# Quick Start

这份指南用于完成一次最小可运行流程。完整规则见根目录 `README.md` 和 `SKILL.md`。

## 1. 安装依赖

```bash
git clone https://github.com/TingYuNya/bank-card-tutorial-video-skill.git
cd bank-card-tutorial-video-skill
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
python scripts/check_env.py
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
python scripts/check_env.py
```

## 2. 准备输入

```text
input/
├── tutorial.md
└── images/
    ├── 01-login.png
    └── 02-activate.png
```

Markdown 中使用相对路径：

```markdown
# 银行卡激活教程

## 登录账户

打开银行官方应用并登录。

![登录页面](images/01-login.png)
```

请先删除或遮挡真实卡号、CVV、验证码、账户号和身份信息。

## 3. 初始化项目

```bash
python scripts/init_project.py \
  --input /absolute/path/to/input/tutorial.md \
  --project /absolute/path/to/project
```

## 4. 生成内容文件

让 Codex 或 Claude Code 读取 `SKILL.md`，完成：

```text
work/fact-check.json
work/privacy-review.json
work/revised-article.md
work/narration.json
work/on-screen-text.md
work/storyboard.json
sources/source-list.md
```

随后执行：

```bash
python scripts/validate_project.py \
  --project /absolute/path/to/project \
  --phase content
```

## 5. 审核分镜

```bash
python scripts/build_review_pages.py --project /absolute/path/to/project
python scripts/serve_preview.py --project /absolute/path/to/project --port 8767
```

打开：

```text
http://127.0.0.1:8767/review/storyboard-audit.html
```

## 6. 配音与时间线

```bash
python scripts/generate_tts.py \
  --project /absolute/path/to/project \
  --provider elevenlabs \
  --reuse

python scripts/build_subtitles.py --project /absolute/path/to/project
python scripts/build_timeline.py --project /absolute/path/to/project
```

打开：

```text
http://127.0.0.1:8767/review/timeline-preview.html
```

## 7. 渲染与验收

```bash
python scripts/validate_project.py \
  --project /absolute/path/to/project \
  --phase render

python scripts/render_final_video.py --project /absolute/path/to/project
python scripts/quality_check.py --project /absolute/path/to/project
```

最终视频默认位于：

```text
renders/银行卡教程-final.mp4
```
