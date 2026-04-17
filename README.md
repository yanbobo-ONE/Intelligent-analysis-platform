# 智能分析系统

## 项目结构

当前项目采用根目录 + `NL2SQLAgent/` 的组织方式，前后端代码统一放在该目录下：

```text
智能分析系统/
├── README.md
└── NL2SQLAgent/
    ├── backend/
    │   ├── app/
    │   └── tests/
    └── frontend/
        ├── src/
        ├── index.html
        ├── package.json
        ├── tsconfig.json
        └── vite.config.ts
```

## 说明

- `NL2SQLAgent/backend/`：后端服务代码，使用 FastAPI 实现。
- `NL2SQLAgent/frontend/`：前端页面代码，使用 React + TypeScript + Vite 实现。
- 根目录 `README.md`：用于说明项目整体结构和开发约定。

## 开发约定

- 后端开发优先在 `NL2SQLAgent/backend/` 中进行。
- 前端开发优先在 `NL2SQLAgent/frontend/` 中进行。
- 计划、规则、任务管理文件继续保留在 `.cursor/` 下。
