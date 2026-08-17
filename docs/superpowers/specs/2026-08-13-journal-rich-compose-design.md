# 知识期刊 · 丰满成刊（导读 / 目录 / 多图示）设计

> Date: 2026-08-13  
> Status: Approved (conversation)  
> Extends: [2026-08-12-knowledge-journal-design.md](./2026-08-12-knowledge-journal-design.md)

## 目标

成刊后期刊读起来**完整、清晰、好扫**：

1. 文案加长、少裁切，一期 **5–6** 张知识卡且 kind 多样  
2. 按内容类型使用不同 **图示**（`diagram.type`）  
3. 增加 **刊首导读页** 与 **目录页**，丰满整期结构  

## 非目标

- 长文杂志正文  
- 目录页可点击跳转（仅静态排版）  
- 外部插画 / AI 生图  
- 改动发布渠道协议  

## 问题诊断

- 成刊 prompt 把 concept 锁在约 80–110 字，example 偏短  
- 预览大量 `-webkit-line-clamp`，读感「缺一块」  
- 图示几乎只有横向 `flow` 四格箭头  
- 无导读/目录，期刊感弱于「一沓同质卡片」  

## 一期页序

| 序 | 页 | 数据来源 |
|----|----|----------|
| 0 | 封面 | `cover` |
| 1 | 导读 | `frontMatter.guide` |
| 2 | 目录 | `frontMatter.toc` |
| 3… | 知识卡 | `knowledge[]`（5–6） |

导出 PNG / 预览栈按此顺序；历史回载保留 `frontMatter`。

## frontMatter schema

```json
{
  "guide": {
    "headline": "本期导读",
    "promises": ["带走点1", "带走点2", "带走点3"],
    "meta": "基于 N 条证据 · 主题…"
  },
  "toc": [
    { "index": 1, "title": "卡标题", "kind": "steps", "diagram": "cycle" }
  ]
}
```

- `promises`：恰好 3 条，每条 ≤28 字，写「读完能做到/看清什么」  
- `toc`：与 `knowledge` 一一对应（成刊后由服务端/normalize 同步，允许用户改 title 后重同步）  

## 知识卡加长 + diagram

### 文案预算（成刊 compose）

| 字段 | 预算 |
|------|------|
| concept | 140–220 字 |
| keyPoint / realPoints | 4–6 条，每条 ≤42 字 |
| example | 90–140 字（场景→动作→产物+数字） |
| topicTitle | ≤14 字 |

### kind 多样性

一期至少覆盖下列中的 **3 类**：`steps` 或 `cycle` 等价、`compare`、`data`、`keypoints`、`quote`。  
目标卡数 **5–6**（normalize clamp）；不足 pad，超出截断到 6。

### diagram

```json
{
  "type": "flow|cycle|compare|stack|callout|bullets",
  "nodes": [{ "label": "≤10字", "note": "可选≤24字" }]
}
```

| type | 适用 | 渲染要点 |
|------|------|----------|
| `flow` | steps | 横向 3–5 节点 + 箭头（加强现有） |
| `cycle` | 编排/回退 | 环形 3–5 节点 |
| `compare` | compare | 左右板；可同步 `compare_left/right` |
| `stack` | 分层能力 | 自下而上 3–4 层 |
| `callout` | data / quote | 大数字或金句主视觉 |
| `bullets` | keypoints | 编号要点轨 |

缺省：按 `card_kind` 推断（steps→flow，compare→compare，data/quote→callout，keypoints→bullets，concept→stack 或 bullets）。  
非法 type → 回退推断。

每卡仍需 `evidenceIds`（选中证据池）；校验逻辑沿用现网。

## LLM 成刊流程调整

1. **大纲**：输出 cover + `guide.promises` + 5–6 选题（含 `card_kind`、`diagram.type`、`evidenceIds`）  
2. **扩写**：按新字数预算与 diagram.nodes；禁止种同质 flow  
3. **normalize**：clamp 卡数、补全 diagram、生成/对齐 `toc`、填充 guide.meta（证据数+主题）  

快扫路径：可仍偏 3–4 卡、可省略导读/目录（`frontMatter` 空则 UI 不插入那两页）；**深成刊**（compose）必须带 frontMatter。

## UI

- 预览栈：封面 →（若有）导读 →（若有）目录 → 知识卡  
- 编辑器：导读三承诺可编辑；目录只读或可改 title（改 title 写回对应 knowledge.topicTitle）  
- 知识卡编辑增加 `diagram.type` 与节点文本  
- 减弱 line-clamp：要点区尽量展示 4–6 条；concept 允许约 6–8 行  

## API / 持久化

- `run_compose` / `compose_with_llm` 返回体增加 `frontMatter`  
- history / InsForge `payload` 已整包存储，无需新表；本地 JSON 原样保存  
- 旧历史无 `frontMatter`：预览仅封面+知识卡（兼容）  

## 测试

- normalize：5–6 卡、diagram 回退、toc 长度=knowledge  
- 缺 frontMatter 的旧 payload 渲染不崩  
- compose mock：promises 长度为 3  
- 回归：research / scan / journal 既有测试  

## 成功标准

- 成刊预览可见导读页与目录页  
- 同期刊至少 3 种图示视觉差异（肉眼可辨）  
- 单卡 concept 明显长于旧版 80–110 字稿，要点 ≥4 条  
- 旧记录无 frontMatter 仍可打开编辑  

## 实现顺序

1. schema + normalize（frontMatter / diagram / 字数）  
2. compose_with_llm 提示词与扩写  
3. cards_workshop 渲染：导读、目录、六类图示、减弱裁切  
4. 编辑器字段 + 导出页序  
5. 测试与工作台冒烟  
