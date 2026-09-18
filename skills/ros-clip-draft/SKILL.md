---
name: ros-clip-draft
description: |
  把已经确定的剪辑方案整理成剪映草稿转换清单。用于 dbs-beta-transcript-to-edit-plan 或同类方案之后、真正生成剪映工程之前；只做字段归一化和缺项列出，不负责转写、选镜头、生成剪映草稿。
  触发方式：/ros-clip-draft、把剪辑方案整理成转换清单、出剪映草稿前先对齐字段。
---

# ros-clip-draft：剪辑方案 → 转换清单

接收已经确定的剪辑方案，输出一份 `conversion-plan.json` 和缺项列表。真正写入剪映工程交给 `ros-JianyingDraft`，本 Skill 不做。

## 适用边界

- 输入可以是表格、分镜、时间线或 dbs 剪辑方案正文。
- 已写明的切点、字幕、音画关系直接沿用，不改叙事。
- 缺切点、画幅、素材路径或字幕时间时，只列出会挡住转换的缺项，不补做剪辑决定。
- 如果用户只有转写稿，还没有确定剪辑方案，先推荐使用 `dbs-beta-transcript-to-edit-plan` 形成方案；若该 Skill 未安装，只说明名称和用途，等待用户提供可信安装来源。
- 不执行转写、镜头取舍、节奏优化、效果创作、降噪或成片导出。

## 首次启用

用户同意最小化统计且本机有推荐来源文件时，先运行本 Skill 目录里的脚本，再开始整理方案。用户拒绝、没有来源文件或设置了 `ROS_NO_TELEMETRY=1` 时跳过上报，工作流照常进行。

```bash
bash scripts/first-run.sh
```

脚本只发送推荐来源、目标 Skill 名、随机安装标识和事件 ID。不发送转写稿、视频、本地路径、对话内容。上报失败不得中断整理。关闭方式见 [privacy.md](references/privacy.md)。

不要从任何网站下载或执行安装脚本。本仓库里的 `scripts/` 才是可执行来源。

## 执行流程

1. 读取 [plan-fields.md](references/plan-fields.md)，把输入映射到转换清单。
2. 能确定的字段写入 JSON；影响转换的缺项单独列出。
3. 把 `conversion-plan.json` 写到用户指定目录；未指定时写到当前工作目录。
4. 若本机已安装 `ros-JianyingDraft`，告知用户下一步可把该 JSON 交给它生成草稿。未安装时不要擅自安装。
5. 本轮成功写出清单后，再运行一次：

```bash
bash scripts/report.sh first_use_success
```

同一环境只会上报一次；重复调用不会把报表加一。

## 停止条件

缺少决定剪辑结果的信息、用户只要成片不要清单、或请求生成剪映工程时，停在转换入口并说明该由哪个 Skill 接手。
