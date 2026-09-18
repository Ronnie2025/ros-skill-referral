# Skill 互推记录

[dbskill.site/referral](https://dbskill.site/referral/) 是通用互推面板，默认显示全部推荐来源与目标 Skill。可以按推荐人 / 渠道、来源 Skill、目标 Skill、活动筛选；每条推荐关系展示去重安装环境数、首次使用数与最近上报时间。新接入的 Skill 无需修改网页。

test-A 根据主题写出完整口播稿，交付后询问是否需要继续做剪辑方案。用户需要时，A 推荐 test-B；同意安装后自动交接当前稿件，由 B 产出分段剪辑方案。这组实验的安装成功上报显示在 [dbskill.site/referral](https://dbskill.site/referral/)。

网站只收数据，不发脚本。Agent 不会被要求执行 `curl 网站 | bash`。

## 示例：两个测试 Skill

| Skill | 角色 | 安装 |
| --- | --- | --- |
| test-A（安装标识 `test-a`） | 写口播，交付后询问是否需要剪辑方案；需要时推荐 B | `npx -y skills add Ronnie2025/ros-skill-referral --skill test-a -g` |
| test-B（安装标识 `test-b`） | 根据口播稿生成剪辑方案，包括节奏、字幕、画面和声音建议 | `npx -y skills add Ronnie2025/ros-skill-referral --skill test-b -g` |

最短测试输入：`/test-a 帮我写一条一分钟的口播，讲为什么企业买了 AI 工具却用不起来。` 用户无需在提示词中指定 B、链接或安装步骤。A 先交付稿件，再一次说明下一步会使用 B、未安装时自动安装并记录最小化统计。用户回复“需要”“做剪辑方案”或“安装”后直接检查、安装、上报并交接，不单独追问统计；用户可回复“不统计”关闭。安装器自身的确认也由已授权流程自动处理，宿主系统权限仍按实际要求执行。

Skill 格式要求小写安装标识，因此安装命令和调用名使用 `test-a` / `test-b`；界面显示名使用 test-A / test-B。旧的 `dbs-recommend-ros-clip` 与 `ros-clip-draft` 保留原样，供已有安装继续使用。test-B 可只凭稿件生成剪辑规划，无需先有录像；产物为剪辑方案，实际剪映工程属于后续制作阶段。

## 统计口径

数字是 **已上报的去重安装环境数**：按 `(installation_id, target_skill)` 去重，由全局首次成功安装上报确定推荐来源，再应用筛选。后续重复安装、换来源上报或网络重试不会重新归因。原始事件数按事件本身的字段筛选，与安装归因口径分开。缺失来源显示为“未记录”，不推断推荐人。客户端上报可被伪造，这项试验数据不能用于分成或核算独立人数。

关闭统计：`export ROS_NO_TELEMETRY=1`。拒绝后仍可安装。

`setup_success` 记录安装核验后的成功上报；`first_use_success` 记录 B 首次完成剪辑方案。上报失败不阻断方案交付。安装和统计已授权时自动继续交接，无需再次粘贴稿件。

## 接入其他 Skill

在用户同意后，由 Skill 自己的安装或启用脚本向 `https://dbskill.site/referral/e` POST JSON。提供以下字段：

| 字段 | 含义 |
| --- | --- |
| `referrer` | 推荐人或渠道标识，例如 `creator-name` |
| `source_skill` | 推荐方 Skill 标识，例如 `writer-helper` |
| `target_skill` | 被推荐方标识，例如 `clip-planner`，必填 |
| `campaign` | 活动标识，例如 `autumn-pilot` |
| `installation_id` | 安装环境内持久保存的随机标识，必填 |
| `event_id` | 事件唯一标识；同一事件重试时复用，必填 |
| `event` | `install_attempt`、`install_success`、`setup_success` 或 `first_use_success` |

标识使用 1–80 位英文字母、数字、点、下划线或连字符。推荐人、来源 Skill、活动可以缺省，完整填写才便于归因；目标 Skill 缺失或非法时返回 400。仅成功安装事件进入安装关系明细，单独的尝试事件只计入原始事件。已存在的历史记录保留。

`GET /referral/stats.json` 默认返回全部汇总；可选查询参数为 `referrer`、`source_skill`、`target_skill`、`campaign`。返回的 `options` 来自全部记录，筛选后仍可切换其他来源。

## 阿里云部署与更新

统计接口由独立 Python 服务处理，Nginx 将 `/referral/` 转发到本机服务。首次部署或更新时，在 ECS 中执行：

```bash
ssh aliyun
# 把本仓库的 site/ 拷到服务器后：
cd /root/ros-skill-referral/site   # 或你放的路径
sudo bash install-on-aliyun.sh
curl -fsS https://dbskill.site/referral/health
```

本机拷文件可以用：

```bash
scp -P 2222 -r site root@112.126.58.198:/root/ros-skill-referral-site
```

装好后打开 https://dbskill.site/referral/ 。首页不会放入口，避免和豆包加载器混在一起。

脚本还会改两处 Nginx，缺一不可：

1. `/etc/nginx/sites-available/dbskill.site`：立刻让 `/referral/` 可访问
2. `/usr/local/libexec/dbskill/nginx/dbskill.site.conf`：全站自动发布用的根模板，避免下次发布把 `/referral/` 冲掉

`dbs-web-loader` 仓库里的 Nginx 模板也已同步改好，但线上真正生效靠上面第 2 步，不靠把这个私有仓库推上去。
