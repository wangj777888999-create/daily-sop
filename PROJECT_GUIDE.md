# 智能工作台平台 - 项目说明文档

> 本文档以 `ui.md` 设计系统为准，技术实现参照 `ui.md` 第12节"快速实现建议"

## 1. 项目概述

### 1.1 项目定位
智能工作台平台是一款面向知识工作者的一体化办公辅助工具，提供 SOP 数据分析、政策报告撰写、高级数据分析、数据库连接、个人知识库五大核心功能。

### 1.2 核心价值
- **模块化设计**：各功能独立又可联动，便于扩展和维护
- **AI 增强**：集成 Claude API，提供智能分析和辅助撰写
- **本地优先**：数据本地存储，保护隐私安全

---

## 2. 设计系统（以 ui.md 为准）

### 2.1 颜色令牌

| 令牌名         | Hex       | 用途                         |
|----------------|-----------|------------------------------|
| `pageBg`       | `#F7F3EC` | 全局页面背景（米白）         |
| `sidebarBg`    | `#EDE7D9` | 左侧导航背景                 |
| `aiPanelBg`    | `#EAE4D6` | 右侧 AI 面板背景             |
| `topbarBg`     | `#FEFCF8` | 顶部导航栏背景               |
| `cardBg`       | `#FEFCF8` | 卡片背景                     |
| `border`       | `#C4BAA8` | 通用边框色                   |
| `textHeading`  | `#3D3530` | 标题文字                     |
| `textBody`     | `#6B5F52` | 正文文字                     |
| `textLight`    | `#9C8E82` | 辅助/次要文字                |
| `accent`       | `#5B8F7A` | 主强调色（鼠尾草绿）         |
| `accentLight`  | `#D6EDE7` | 主强调色浅底                 |
| `amber`        | `#C17F3A` | 次强调色（暖琥珀）           |
| `blue`         | `#3A7FC1` | 功能色（数据库/Word）        |
| `purple`       | `#7B6BAA` | 功能色（高级分析）           |
| `placeholder`  | `#DDD6C8` | 占位块背景                   |
| `chip`         | `#E5DDD0` | 标签/Chip 背景               |

### 2.2 字体

```
字体栈：-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif

标题大：  20px / Bold (700) / color: textHeading
标题中：  16px / Bold (700) / color: textHeading
标题小：  14px / Bold (700) / color: textHeading
正文：    13px / Regular (400) / color: textBody
辅助文字：12px / Regular (400) / color: textLight
标签文字：11px / Regular (400)
微标签：  10px / Bold (700)
```

### 2.3 间距基准

基准单位：**8px**

| 间距 | 值     | 使用场景            |
|------|--------|---------------------|
| xs   | 4px    | 图标与文字间距       |
| sm   | 8px    | 组件内部紧凑间距     |
| md   | 12px   | 卡片内部 padding     |
| lg   | 14px   | 列与列之间 gap       |
| xl   | 20px   | 页面主区域 padding   |

### 2.4 圆角

| 级别   | 值    | 使用场景             |
|--------|-------|----------------------|
| small  | 6px   | Chip、标签、输入框   |
| medium | 8px   | 按钮、导航项         |
| large  | 10px  | 卡片                 |
| xlarge | 12px  | 大型搜索框、弹层     |
| circle | 50%   | 头像                 |

---

## 3. 技术架构

### 3.1 技术栈

| 类别 | 技术选型 | 说明 |
|------|----------|------|
| 前端框架 | Streamlit | 快速开发、数据展示强 |
| AI 引擎 | Claude API | 智能分析和生成 |
| 数据处理 | Pandas + SQLAlchemy | 数据分析和 ORM |
| 向量存储 | ChromaDB（默认） | 轻量级向量数据库 |
| Python 版本 | 3.11+ | 现代 Python 特性 |

### 3.2 项目结构

```
ai_analyst_v2/
├── app_main.py              # Streamlit 多页面入口
├── core/                    # 核心模块
│   ├── agent.py             # AI Agent 核心
│   ├── code_executor.py     # Python 代码执行器
│   └── memory.py            # 记忆模块
├── domain/                  # 领域层（DDD）
│   ├── entities/            # 实体定义
│   └── interfaces/         # 接口定义
├── use_cases/               # 用例层
├── adapters/                # 适配器层
├── infrastructure/          # 基础设施层
│   └── di_container.py      # 依赖注入容器
├── tools/                   # 工具集
│   ├── chart_builder.py     # 图表构建
│   ├── data_profiler.py     # 数据探查
│   ├── question_suggester.py# 问题建议
│   └── sql_connector.py     # SQL 连接器
└── ui/                      # UI 层
    ├── theme.py             # 主题配置（ui.md 设计系统）
    ├── components.py        # 公共组件
    └── pages/               # 页面模块
        ├── home.py          # 首页/工作台
        ├── sop.py           # SOP 数据分析
        ├── policy.py        # 政策报告撰写
        ├── analytics.py     # 高级数据分析
        ├── database.py      # 数据库连接
        └── knowledge.py     # 个人知识库
```

### 3.3 分层设计（Clean Architecture）

| 层级 | 职责 | 包含内容 |
|------|------|----------|
| Domain | 业务实体和规则 | entities/, interfaces/ |
| Use Cases | 业务用例实现 | 各模块的 service.py |
| Adapters | 外部服务适配 | API 适配器、数据适配器 |
| Infrastructure | 基础设施 | DI 容器、配置、数据库 |
| UI | 用户界面 | Streamlit 页面、组件 |

---

## 4. 功能模块

### 4.1 首页（home）

**入口**：`/` 或 `/home`

**功能**：
- 服务卡片网格（变体A）：6张服务卡片快速入口
- 仪表盘概览（变体B）：指标卡片 + 趋势图 + 近期任务

**路由**：`/` → 首页 `/home` → 仪表盘

### 4.2 SOP 数据分析（sop）

**入口**：`/sop`

**功能**：
- 步骤向导（变体A）：4步流程引导
- 分屏操作台（变体B）：数据预览 + SOP 配置

**状态**：`currentStep (1-4)`, `selectedTemplate`, `analysisStatus`

### 4.3 政策报告撰写（policy）

**入口**：`/policy`

**功能**：
- 文档编辑器（变体A）：三栏布局（大纲 + 编辑器 + 信息）
- 引导式流程（变体B）：4步流程引导

**状态**：`reportStep (1-4)`, `outline`, `wordCount`, `autoSave`

### 4.4 高级数据分析（analytics）

**入口**：`/analytics`

**功能**：
- 图表仪表盘（变体A）：2x2 图表网格
- 对话驱动分析（变体B）：自然语言查询

### 4.5 数据库连接（database）

**入口**：`/database`

**功能**：
- SQL 编辑器（变体A）：语法高亮 + 查询结果
- 可视化查询构建器（变体B）：拖拽建表 + JOIN

**状态**：`activeConnection`, `queryText`, `queryResult`, `queryHistory`

### 4.6 个人知识库（knowledge）

**入口**：`/knowledge`

**功能**：
- 文件浏览器（变体A）：文件夹树 + 文件网格
- 搜索优先（变体B）：语义搜索 + 结果列表

**状态**：`currentFolder`, `searchQuery`, `searchMode`, `viewMode`

---

## 5. 全局组件

### 5.1 AI 助理面板

**位置**：页面最右侧，固定宽度 280px，全高始终可见

**结构**：
- 顶部标题栏（绿色圆点 + "AI 助理" + Claude 徽章）
- 对话区（消息气泡 + typing 指示）
- 快捷操作区（Chip 行）
- 输入框（带发送按钮）

### 5.2 通用组件

| 组件 | 规范 |
|------|------|
| Card | background: cardBg; border: 1px solid border; border-radius: 10px; padding: 14px |
| Primary Button | background: accent; color: white; padding: 8px 18px; border-radius: 8px |
| Secondary Button | background: chip; color: textBody; padding: 8px 18px; border-radius: 8px |
| Chip | background: chip; border: 1px solid border; padding: 4px 9px; border-radius: 6px |
| MetricCard | WCard 样式 + label/value/delta 三行布局 |
| StepBadge | 圆形序号 + 文字 + 连接线 |
| Input | background: pageBg; border: 1px solid border; border-radius: 6px |

---

## 6. 开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 1：架构设计 | ✅ 完成 | Clean Architecture 规划 |
| 阶段 2：UI 设计 | ✅ 完成 | ui.md 设计系统 |
| 阶段 3：框架搭建 | 🔄 进行中 | 六模块框架 + 通用组件 |
| 阶段 4：业务实现 | ⏳ 待开始 | 各模块具体业务逻辑 |
| 阶段 5：测试部署 | ⏳ 待开始 | 测试和部署 |

---

*文档版本：v2.0 · 更新于 2026-04-23 · 以 ui.md 设计系统为准*
