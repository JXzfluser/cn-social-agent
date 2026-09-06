# 内容生成模块优化需求

## 问题分析

### P0 - 平台列表不一致

#### 现状

| 模块 | 平台列表 |
|------|----------|
| 内容生成表单 | 朋友圈、微博、小红书、公众号、抖音、知乎 |
| 平台配置模块 | 钉钉、飞书、企业微信、微信公众号、微博、小红书、抖音 |
| 一稿多发模块 | 微博、微信公众号、小红书、抖音、知乎 |

#### 问题

1. 内容生成的"朋友圈"在平台配置中不存在
2. 平台配置的"钉钉、飞书、企业微信"在内容生成中不可选
3. 生成表单不检查平台是否已配置，用户可能选择未配置的平台

#### 解决方案

**统一平台数据源**

```
// 新增统一平台配置常量
const PLATFORMS = [
    { id: 'dingtalk', name: '钉钉', icon: '钉', color: '#1677ff', hasPublishApi: true },
    { id: 'feishu', name: '飞书', icon: '飞', color: '#00b42a', hasPublishApi: true },
    { id: 'wecom', name: '企业微信', icon: '企', color: '#12a0ff', hasPublishApi: true },
    { id: 'weixin', name: '微信公众号', icon: '微', color: '#52c41a', hasPublishApi: true },
    { id: 'weibo', name: '微博', icon: '微', color: '#ff6a00', hasPublishApi: false },
    { id: 'xiaohongshu', name: '小红书', icon: '小', color: '#ff4d4f', hasPublishApi: false },
    { id: 'douyin', name: '抖音', icon: '抖', color: '#1a1a1a', hasPublishApi: false },
    { id: 'zhihu', name: '知乎', icon: '知', color: '#0066ff', hasPublishApi: false },
    { id: 'pengyouquan', name: '朋友圈', icon: '朋', color: '#07c160', hasPublishApi: false },
];
```

**内容生成表单改造**

1. 动态加载平台列表
2. 显示平台配置状态（已配置/未配置）
3. 未配置平台可选但提示用户配置

```html
<select id="gen-platform" class="form-input">
    <!-- 动态渲染 -->
    <option value="weibo" data-status="not_configured">微博 (未配置)</option>
    <option value="feishu" data-status="connected">飞书 ✓</option>
</select>
```

**后端接口**

```python
GET /api/platforms/available
返回:
{
    "platforms": [
        {"id": "feishu", "name": "飞书", "status": "connected", "has_publish_api": true},
        {"id": "weibo", "name": "微博", "status": "not_configured", "has_publish_api": false}
    ]
}
```

---

### P1 - 多媒体内容支持

#### 现状

- 内容生成仅支持文本输入
- 后端 `_Post` 数据类有 `images` 字段但前端未使用
- 一稿多发不保留媒体内容

#### 解决方案

**内容生成表单增强**

```html
<div class="form-group">
    <label>内容/主题</label>
    <textarea id="gen-content" rows="4"></textarea>
</div>

<div class="form-group">
    <label>图片 (可选)</label>
    <div class="upload-area" id="gen-images-upload">
        <input type="file" id="gen-images" multiple accept="image/*">
        <div class="upload-placeholder">
            <svg>...</svg>
            <span>点击或拖拽上传图片</span>
        </div>
        <div class="upload-preview" id="gen-images-preview"></div>
    </div>
</div>

<div class="form-group">
    <label>视频链接 (可选)</label>
    <input type="url" id="gen-video-url" placeholder="https://...">
</div>
```

**数据结构**

```javascript
{
    content: "文本内容",
    images: ["base64_or_url_1", "base64_or_url_2"],
    video_url: "https://...",
    platform: "xiaohongshu",
    style: "专业"
}
```

**一稿多发媒体保留**

```python
# 后端改写时保留媒体
results[platform] = {
    "rewritten": rewritten_text,
    "images": original_images,  # 保留原图
    "video_url": original_video  # 保留视频
}
```

---

## 实施优先级

| 优先级 | 需求 | 工作量 |
|--------|------|--------|
| P0 | 平台列表统一 + 状态显示 | 2天 |
| P1 | 图片上传支持 | 1天 |
| P1 | 视频链接支持 | 0.5天 |
| P2 | 一稿多发媒体保留 | 1天 |

---

## 验收标准

### P0 平台统一

- [ ] 内容生成平台下拉动态加载
- [ ] 显示平台配置状态
- [ ] 未配置平台有提示
- [ ] 一稿多发平台列表一致

### P1 多媒体

- [ ] 支持图片上传预览
- [ ] 支持视频链接输入
- [ ] 生成结果包含媒体信息
- [ ] 一稿多发保留媒体内容
