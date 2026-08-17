# 微信公众号贴图发布配置

## 凭证（优先写入 InsForge Secrets）

启动 workbench 时，若 `.env` 中配置了 `WEIXIN_APP_ID` / `WEIXIN_APP_SECRET`，会自动同步到 InsForge Secrets（key: `card_plat_cfg_weixin`），并镜像到 `data/oauth/config/weixin.json`。

用户 OAuth / 授权标记：`card_oauth_weixin_{owner}`。

InsForge 不可用时降级为本地 `data/oauth/`。

## 公众号后台

1. 开通**草稿箱 / 发布**权限的服务号或订阅号（需认证）
2. IP 白名单加入服务器出口 IP
3. 配置 AppID / AppSecret 到 `.env` 后重启 workbench

## 发布行为

- 默认写入**草稿**（贴图 HTML：封面 + 知识点 PNG）
- 勾选「直接发布」时调用 freepublish；失败则保留草稿并提示

## 可选

- `WEIXIN_DRAFT_AUTHOR`：草稿作者显示名
- `OAUTH_PUBLIC_BASE`：外网回调基址（穿透/生产）
