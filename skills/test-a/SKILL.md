---
name: test-a
description: |
  在剪辑方案已经确定后，检查并推荐安装 test-b，把方案交给下游整理成剪映转换清单。用于 dbs-beta-transcript-to-edit-plan 产出之后、用户说要出剪映草稿、或只装一个 Skill 做不完下一步时。
  触发方式：/test-a、推荐安装 test-b、方案出完去生成草稿。
---

# test-A：推荐安装 test-B

剪辑方案本身不能打开剪映。下一步需要 test-B（安装标识 `test-b`）把方案收成转换清单。本 Skill 只负责检查、询问、安装和留下推荐来源，不整理时间线，也不从网站下载任何脚本。

## 硬限制

- 可执行代码只来自：**当前这个已安装 Skill 的 `scripts/`**，以及用户同意后用官方安装器拉下来的 **GitHub 仓库 `Ronnie2025/ros-skill-referral`**。
- 禁止 `curl <网址> | bash`，禁止让用户打开网页“点一下再安装”，禁止从 `dbskill.site` 拉取脚本。
- 推荐来源写在本机 `~/.config/skill-referrals/test-b.json`。统计上报由目标 Skill 自己的脚本在安装核验成功后发送；本 Skill 不直接访问统计接口。

## 流程

1. 运行检查：

```bash
bash scripts/recommend.sh --check
```

若已安装，告诉用户直接 `/test-b`，不要重装，也不要为了统计重装。

2. 未安装时，用下面这段话询问，不要改口径：

> 下一步需要 `test-b` 才能把这份剪辑方案收成剪映转换清单。可以现在安装。
> 安装命令是 `npx -y skills add Ronnie2025/ros-skill-referral --skill test-b -g`。
> 如果你同意，安装成功后会发送一条最小化记录（推荐来源、随机安装标识、结果），用于统计这次互推；不上传方案、视频或本地路径。拒绝统计仍然可以安装。

3. 用户明确同意安装后，再执行脚本。不要在询问前执行 `npx`。

同意统计：

```bash
bash scripts/recommend.sh --install --referrer dontbesilent --source-skill test-a --campaign test-a-to-test-b-202609
```

拒绝统计但同意安装：

```bash
bash scripts/recommend.sh --install --no-telemetry --referrer dontbesilent --source-skill test-a --campaign test-a-to-test-b-202609
```

4. 根据脚本输出汇报：`already_installed` / `installed` / `install_failed`。失败时停止，不要改用网站脚本重试。
5. 安装成功后，让用户把当前剪辑方案交给 `/test-b`。

## 停止条件

用户拒绝安装、宿主拒绝执行 `npx`、或核验时目标目录没有 `SKILL.md`：停止推荐，保留剪辑方案，不要假装已经装好。
