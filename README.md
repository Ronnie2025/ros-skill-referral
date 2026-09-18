# Skill 互推 MVP

test-A 根据主题写出完整口播稿，交付后询问是否需要继续做剪辑方案。用户需要时，A 推荐 test-B；同意安装后自动交接当前稿件，由 B 产出分段剪辑方案。这组实验的安装成功上报显示在 [dbskill.site/referral](https://dbskill.site/referral/)。

网站只收数据，不发脚本。Agent 不会被要求执行 `curl 网站 | bash`。

## 两个 Skill

| Skill | 角色 | 安装 |
| --- | --- | --- |
| test-A（安装标识 `test-a`） | 写口播，交付后询问是否需要剪辑方案；需要时推荐 B | `npx -y skills add Ronnie2025/ros-skill-referral --skill test-a -g` |
| test-B（安装标识 `test-b`） | 根据口播稿生成剪辑方案，包括节奏、字幕、画面和声音建议 | `npx -y skills add Ronnie2025/ros-skill-referral --skill test-b -g` |

最短测试输入：`/test-a 帮我写一条一分钟的口播，讲为什么企业买了 AI 工具却用不起来。` 用户无需在提示词中指定 B、链接或安装步骤。A 先交付稿件，再询问是否需要剪辑方案；用户回复需要后，才检查 B 并介绍安装和统计选项。仅回答需要剪辑，不授权安装或统计。

Skill 格式要求小写安装标识，因此安装命令和调用名使用 `test-a` / `test-b`；界面显示名使用 test-A / test-B。旧的 `dbs-recommend-ros-clip` 与 `ros-clip-draft` 保留原样，供已有安装继续使用。test-B 可只凭稿件生成剪辑规划，无需先有录像；产物为剪辑方案，实际剪映工程属于后续制作阶段。

## 统计口径

面板仅显示来源 Skill 为 `test-a`、目标 Skill 为 `test-b` 的数据。数字是 **已上报的去重安装环境数**：同一安装环境首次 `setup_success` 记一次。重复安装、网络重试、拒绝统计、断网上报失败均不计入。客户端上报可被伪造，这项试验数据不能用于分成或核算独立人数。

关闭统计：`export ROS_NO_TELEMETRY=1`。拒绝后仍可安装。

`setup_success` 记录安装核验后的成功上报；`first_use_success` 记录 B 首次完成剪辑方案。上报失败不阻断方案交付。安装和统计已授权时自动继续交接，无需再次粘贴稿件。

## 阿里云（你需要做的）

`dbskill.site` 现在是纯静态 Nginx。统计接口要单独起一个本机 Python 服务。SSH 到 ECS 后：

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
