# Contributing

欢迎提交问题、文档修正和代码改进。参与前请阅读 `CODE_OF_CONDUCT.md`、`SECURITY.md` 和 `DISCLAIMER.md`。

## 开发环境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/check_env.py
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/check_env.py
```

## 兼容性要求

1. 完整保留现有配置项、默认值、事实核验字段、隐私字段、分镜逻辑和 UI 样式。
2. 新增功能时同步更新 `SKILL.md`、README 和相关数据契约。
3. 变更数据结构时提供兼容读取或明确迁移步骤。
4. 修改字幕、画布或渲染逻辑时，对照时间线预览和最终关键帧。
5. 新增 TTS 提供商时保留现有提供商与缓存行为。

## 安全与隐私

禁止提交：

1. `.env`、API Key、Token、私钥和真实服务凭据。
2. 完整银行卡号、CVV、PIN、验证码和账户号。
3. 身份文件、未脱敏账单、交易记录和详细地址。
4. 未经授权的付费字体、音乐、声音或图片。

示例必须使用虚构数据或完成脱敏。发现漏洞或敏感信息泄露时，请按照 `SECURITY.md` 私密报告。

## 提交前检查

```bash
python -m compileall scripts
python scripts/check_env.py
```

根据改动范围继续执行：

1. Markdown 初始化与阶段校验。
2. 分镜审核页交互检查。
3. 时间线播放、拖动和倍速检查。
4. Playwright 最终渲染。
5. ffprobe、逐场景关键帧和 contact sheet 验收。

## Pull Request

Pull Request 应说明：

1. 改动范围和原因。
2. 用户可见行为与兼容性影响。
3. 测试命令和结果。
4. 配置或数据结构迁移步骤。
5. 文档更新情况。

仓库提供 `.github/pull_request_template.md` 作为检查模板。用户可见变更应同步写入 `CHANGELOG.md`。
