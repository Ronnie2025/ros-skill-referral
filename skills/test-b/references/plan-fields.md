# 转换清单字段

输出 JSON 使用 `schema_version: 1`。时间一律用秒，保留到微秒，不要写成时间码。

## 必填

| 字段 | 含义 |
| --- | --- |
| `name` | 草稿名称 |
| `canvas.width` / `canvas.height` / `canvas.fps` | 画幅与帧率，fps 仅 24/25/30/50/60 |
| `assets[]` | `id,path,kind`，kind 为 video/audio/image |
| `tracks[]` | 从底到顶；type 为 video/audio/text |

## 片段

- 视频/音频：`id,asset,source_in,source_out,target_start,speed,volume`
- 图片：`id,asset,target_start,duration`
- 文字：`id,text,time_basis,start,end`；`time_basis` 为 `timeline` 或 `source`（source 时必须有 `clip_id`）

## 缺项怎么写

不要编造路径或切点。用数组列出：

```json
{
  "blocking_gaps": [
    {"field": "assets[0].path", "reason": "方案只给了素材名，没有本机路径"}
  ]
}
```

有任何 `blocking_gaps` 时，仍可输出已确定部分，但明确告诉用户还不能交给 `ros-JianyingDraft` 生成工程。
