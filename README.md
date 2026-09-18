# Skill 互推 MVP

两个 Skill 互相推荐安装，并把「来自 dontbesilent 的成功安装」记到 [dbskill.site/referral](https://dbskill.site/referral/)。

网站只收数据，不发脚本。Agent 不会被要求执行 `curl 网站 | bash`。

## 两个 Skill

| Skill | 角色 | 安装 |
| --- | --- | --- |
| `dbs-recommend-ros-clip` | 推荐方：方案出完后检查并询问是否安装下游 | `npx -y skills add Ronnie2025/ros-skill-referral --skill dbs-recommend-ros-clip -g` |
| `ros-clip-draft` | 被推方：把剪辑方案收成转换清单，安装核验成功后上报 | `npx -y skills add Ronnie2025/ros-skill-referral --skill ros-clip-draft -g` |

给栋哥的最短用法：先装推荐 Skill。用户跑完 `dbs-beta-transcript-to-edit-plan` 后说「出草稿」，Agent 应按 `dbs-recommend-ros-clip` 询问，用户同意后再执行仓库里的 `scripts/recommend.sh`。

## 统计口径

面板数字是 **去重安装环境数**：同一台机器首次 `setup_success` 记一次。重复安装、网络重试、拒绝统计、断网上报失败，都不会当成新用户。

关闭统计：`export ROS_NO_TELEMETRY=1`。拒绝后仍可安装。

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
