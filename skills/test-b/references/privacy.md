# 统计与关闭

用户同意统计、且本机有推荐来源文件时，安装或首次使用会向 `https://dbskill.site/referral/e` 发送一条 JSON。没有来源文件时不发送。

- `event`：`setup_success` 或 `first_use_success`
- `referrer` / `source_skill` / `campaign`：来自本机 `~/.config/skill-referrals/test-b.json`
- `target_skill`：固定为 `test-b`
- `installation_id`：本机随机生成，存在 `~/.cache/test-b/install-id`
- `event_id`：单次事件随机 ID，用于防止网络重试重复入库

不发送：转写稿、视频、字幕、本地路径、用户名、对话、机器序列号。

关闭统计（安装和使用都不受影响）：

```bash
export ROS_NO_TELEMETRY=1
```

也可以删除 `~/.config/skill-referrals/test-b.json`，之后不再上报。推荐方的 `--no-telemetry` 选项会清除这个文件。

服务端会保存访问 IP 的哈希，用于粗糙防刷，不在公开面板展示。
