# 统计与关闭

安装或首次使用时，如果用户没有拒绝，脚本会向 `https://dbskill.site/referral/e` 发送一条 JSON：

- `event`：`setup_success` 或 `first_use_success`
- `referrer` / `source_skill` / `campaign`：来自本机 `~/.config/skill-referrals/ros-clip-draft.json`，没有该文件则留空
- `target_skill`：固定为 `ros-clip-draft`
- `installation_id`：本机随机生成，存在 `~/.cache/ros-clip-draft/install-id`
- `event_id`：单次事件随机 ID，用于防止网络重试重复入库

不发送：转写稿、视频、字幕、本地路径、用户名、对话、机器序列号。

关闭统计（安装和使用都不受影响）：

```bash
export ROS_NO_TELEMETRY=1
```

或删除 `~/.config/skill-referrals/ros-clip-draft.json` 后，以后上报不再带推荐来源。

服务端会保存访问 IP 的哈希，用于粗糙防刷，不在公开面板展示。
