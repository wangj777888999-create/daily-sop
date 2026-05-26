# 数据库全览功能设计

**日期：** 2026-05-26  
**状态：** 已确认，待实现  
**目标用户：** 非技术背景的业务使用者，持有只读数据库权限，需要快速理解数据库结构

---

## 背景与目标

用户拿到数据库只读权限后，面对几十张表不知从何入手。目标是在现有数据库页面中新增「数据库全览」Tab，让用户无需编写 SQL 即可：

1. 一眼看清所有表及其规模
2. 通过样本数据理解每张表存了什么
3. 通过 AI 获得每张表用途的一句话摘要
4. 为自己熟悉的表添加备注，积累理解

---

## 入口

在 `DatabasePage.vue` 的 Tab 栏新增第三个 Tab：**数据库全览**（仅连接数据库后可用）

---

## 视图一：卡片视图（默认）

### 顶部统计栏（4 个数字卡片）
| 字段 | 来源 |
|------|------|
| 当前数据库名 + 连接类型 | `connStatus` |
| 数据表总数 | `GET /database/tables` 结果长度 |
| 已添加备注的表数量 + 进度条 | localStorage |
| 数据量最大的表名 + 行数 | 扫描时 `SELECT COUNT(*)` |

### 工具栏
- 搜索框：实时过滤，匹配表名 / 字段名 / 备注内容
- 标签筛选徽章：全部 / 用户 / 订单 / 日志 / 配置（前端按关键词自动归类，可手动修改）
- 视图切换：卡片 ⇄ 详情
- **✨ AI 一键解读** 按钮：批量为无备注的表生成摘要

### 表卡片
每张表显示：
- 表名
- 行数 + 字段数（灰色徽章）
- AI 摘要（绿色背景，有则显示，无则显示「点击添加备注」占位文字）
- 主要字段标签（最多显示 5 个，超出显示 +N）
- 异常检测：表名含 `fix`、`tmp`、`bak`、`test` 前缀时显示橙色「疑似临时表」徽章

---

## 视图二：详情视图

### 左侧表列表（宽 260px）
- 显示所有表名 + 行数
- 支持搜索过滤
- 点击切换右侧内容

### 右侧详情面板（三个 Card）

**Card 1：AI 解读**
- 绿色背景卡片，显示 AI 生成的一句话描述
- 未生成时显示「点击生成」按钮

**Card 2：字段结构**
- 每行：🔑（主键标识）+ 字段名 + 类型 + 是否 NOT NULL
- 数据来源：`GET /database/columns/{table}`

**Card 3：样本数据**
- 标题「前 5 行」
- 横向可滚动数据表格
- SQL：`SELECT * FROM \`table\` LIMIT 5`

**Card 4：我的备注**
- 多行文本输入框
- 「保存」按钮 → 写入 localStorage
- key：`db_table_notes_${connStatus.display_name}_${tableName}`

---

## AI 解读功能

### 触发方式
1. 单张表：详情视图中点击「生成」
2. 批量：卡片视图顶部「✨ AI 一键解读」，逐张处理无摘要的表

### 实现方案
- 调用现有后端 `/api/generate`（知识库 RAG 接口），或新增一个轻量接口
- Prompt 模板：
  ```
  数据库表名：{table_name}
  字段列表：{col1}({type1}), {col2}({type2}), ...
  
  请用一句话（20字以内）描述这张表是用来存什么数据的。直接输出描述，不要加任何前缀。
  ```
- 结果存 localStorage，key：`db_table_ai_${connStatus.display_name}_${tableName}`
- 已有缓存则直接读取，不重复调用

### 后端接口选择
优先复用 `/api/knowledge/generate`（已有）；若不合适，新增 `POST /api/database/describe-table`

---

## 数据扫描策略

「数据库全览」Tab 激活时触发一次扫描：
1. 已有 `tables` 列表（来自侧边栏），直接复用
2. 并发获取所有表的 `COUNT(*)`（限制并发数 ≤ 5，防止数据库压力过大）
3. `columns` 数据按需懒加载（点击卡片 / 切换详情时才获取）
4. 扫描结果缓存在内存（页面内有效），不持久化

---

## 本地持久化（localStorage）

| Key 格式 | 内容 |
|----------|------|
| `db_table_notes_{displayName}_{table}` | 用户备注文本 |
| `db_table_ai_{displayName}_{table}` | AI 生成摘要 |
| `db_table_tags_{displayName}_{table}` | 用户手动设置的标签（可选，后期扩展） |

---

## 文件改动范围

| 文件 | 改动类型 |
|------|----------|
| `src/ui/pages/database/DatabasePage.vue` | 新增 Tab + 引入新组件 |
| `src/ui/components/database/DbOverviewPanel.vue` | 新建：全览面板主组件 |
| `src/ui/components/database/DbTableCard.vue` | 新建：单张表卡片 |
| `src/ui/components/database/DbTableDetail.vue` | 新建：详情视图右侧面板 |
| `backend/api/database_routes.py` | 可选：新增 `describe-table` 接口 |

---

## 不做的事（YAGNI）

- ❌ ER 图 / 表关系可视化（需要分析外键，复杂度高，业务价值待验证）
- ❌ 表数据编辑（只读权限，不需要）
- ❌ 多数据库对比视图
- ❌ 自动标签分类的 AI 训练（规则关键词已够用）
