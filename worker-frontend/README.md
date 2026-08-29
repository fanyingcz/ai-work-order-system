# 维修工人工作台前端

面向维修工人的独立前端页面，与主前端（frontend/）分离部署。

## 功能

- **工人登录**：使用工人姓名（用户名）+ 工人ID（密码）登录
- **我的工单**：只显示指派给当前登录工人的工单（按 worker_id 过滤）
- **状态筛选**：全部 / 待处理 / 处理中 / 工人完成 / 已完成
- **开始处理**：待处理（PENDING）→ 处理中（processing）
- **完成处理**：处理中（processing）→ 工人完成处理（worker_completed）
- **工单详情**：弹窗查看工单详情

## 工单状态流转

```
PENDING（待处理）--开始处理--> processing（处理中）--工人完成--> worker_completed（工人完成处理）--管理员确认--> completed（已完成）
```

## 启动方式

```bash
cd worker-frontend
npm install
npm run dev
```

默认端口：**5174**（与主前端 5173 不同）

## API 代理

开发环境通过 Vite 代理将 `/api` 请求转发到 `http://127.0.0.1:8000`。

修改 `vite.config.js` 中的 `server.port` 可更改端口。

## 登录方式

- 用户名：`workers` 表中的 `name` 字段（工人姓名）
- 密码：`workers` 表中的 `id` 字段（工人ID）