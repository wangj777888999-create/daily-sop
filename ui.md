# 智能工作台平台 — 前端设计交付文档

> **说明**：本文档配套的 HTML 文件（`wireframe.html`）是使用原型工具制作的**设计参考稿**，展示了布局结构、组件排列和交互逻辑。你的任务是参照本文档和 HTML 参考稿，在目标技术栈（Streamlit / React / Vue 等）中**还原**这套 UI，而非直接使用 HTML 文件。

> **保真度**：线框图（Low-fidelity Wireframe）。颜色、间距已明确定义，请严格遵循；图表等占位区域需替换为真实组件。

---

## 目录

1. [设计系统 / 令牌](#1-设计系统--令牌)
2. [整体页面框架](#2-整体页面框架)
3. [首页 / 工作台](#3-首页--工作台)
4. [SOP 数据分析](#4-sop-数据分析)
5. [政策报告撰写](#5-政策报告撰写)
6. [高级数据分析](#6-高级数据分析)
7. [数据库连接](#7-数据库连接)
8. [个人知识库](#8-个人知识库)
9. [AI 助理面板](#9-ai-助理面板)
10. [通用组件规范](#10-通用组件规范)
11. [交互与状态管理](#11-交互与状态管理)
12. [文件清单](#12-文件清单)

---

## 1. 设计系统 / 令牌

### 1.1 颜色

| 令牌名         | Hex       | 用途                         |
|----------------|-----------|------------------------------|
| `pageBg`       | `#F7F3EC` | 全局页面背景（米白）         |
| `sidebarBg`    | `#EDE7D9` | 左侧导航背景                 |
| `aiPanelBg`    | `#EAE4D6` | 右侧 AI 面板背景             |
| `topbarBg`     | `#FEFCF8` | 顶部导航栏背景               |
| `cardBg`       | `#FEFCF8` | 卡片背景（同 white）         |
| `border`       | `#C4BAA8` | 通用边框色                   |
| `textHeading`  | `#3D3530` | 标题文字                     |
| `textBody`     | `#6B5F52` | 正文文字                     |
| `textLight`    | `#9C8E82` | 辅助/次要文字                |
| `accent`       | `#5B8F7A` | 主强调色（鼠尾草绿）         |
| `accentLight`  | `#D6EDE7` | 主强调色浅底（用于徽章/高亮）|
| `amber`        | `#C17F3A` | 次强调色（暖琥珀）           |
| `blue`         | `#3A7FC1` | 功能色（数据库/Word）        |
| `purple`       | `#7B6BAA` | 功能色（高级分析）           |
| `placeholder`  | `#DDD6C8` | 占位块背景                   |
| `placeholderDk`| `#C8BFB0` | 深色占位（头像等）           |
| `chip`         | `#E5DDD0` | 标签/Chip 背景               |

### 1.2 字体

```
主字体：系统默认无衬线字体
字体栈：-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif

标题大：  20px / Bold (700) / color: textHeading
标题中：  16px / Bold (700) / color: textHeading  
标题小：  14px / Bold (700) / color: textHeading
正文：    13px / Regular (400) / color: textBody
辅助文字：12px / Regular (400) / color: textLight
标签文字：11px / Regular (400)
微标签：  10px / Bold (700)（字母间距 1px）
```

### 1.3 间距基准

基准单位：**8px**

| 间距 | 值     | 使用场景            |
|------|--------|---------------------|
| xs   | 4px    | 图标与文字间距       |
| sm   | 8px    | 组件内部紧凑间距     |
| md   | 12px   | 卡片内部 padding     |
| lg   | 14px   | 列与列之间 gap       |
| xl   | 20px   | 页面主区域 padding   |

### 1.4 圆角

| 级别   | 值    | 使用场景             |
|--------|-------|----------------------|
| small  | 6px   | Chip、标签、输入框   |
| medium | 8px   | 按钮、导航项         |
| large  | 10px  | 卡片                 |
| xlarge | 12px  | 大型搜索框、弹层     |
| circle | 50%   | 头像                 |

### 1.5 阴影

```
卡片默认：无阴影（依靠 border 区分层级）
悬浮卡片/弹出层：box-shadow: 0 4px 16px rgba(61, 53, 48, 0.10)
焦点输入框：box-shadow: 0 0 0 2px #5B8F7A40
```

---

## 2. 整体页面框架

### 2.1 布局结构

```
┌─────────────────────────────────────────────────────┐
│                    顶部导航栏 (52px)                  │
├──────────┬──────────────────────────┬───────────────┤
│          │                          │               │
│  左侧    │      主内容区            │  AI 助理      │
│  导航    │      (flex: 1)           │  面板         │
│  (220px) │                          │  (280px)      │
│          │                          │               │
└──────────┴──────────────────────────┴───────────────┘
```

**实现要点：**
- 整体使用 `display: flex; height: 100vh` 的全屏三列布局
- 左侧导航和右侧 AI 面板**固定宽度、固定位置**，不随内容滚动
- 主内容区 `flex: 1; overflow-y: auto`，内部 padding `20px`
- 顶部导航栏高度固定 `52px`，在主内容列内部处于顶部

### 2.2 左侧导航栏规范

**容器：** `width: 220px; background: #EDE7D9; border-right: 1px solid #C4BAA8`

**Logo 区域（顶部）：**
```
padding: 18px 16px
border-bottom: 1px solid #C4BAA8
内容：
  - 图标块：34×34px, borderRadius: 9px, background: #5B8F7A, 内含品牌图标（白色）
  - 右侧两行文字：
      主：13px Bold "智能工作台"
      副：10px Regular "AI Workbench v2" color: #9C8E82
```

**导航列表：**
```
padding: 10px 8px
分组标签：9px, letterSpacing: 1px, color: #9C8E82, padding: 4px 10px 6px

导航项：
  padding: 9px 12px
  borderRadius: 8px
  marginBottom: 2px
  fontSize: 13px
  
  默认状态：
    background: transparent
    color: #6B5F52
    
  激活状态（当前页）：
    background: #5B8F7A
    color: #ffffff
    右侧显示一个小圆点 (6px, rgba(255,255,255,0.6))

导航项列表（icon + label）：
  ⌂  工作台首页     key: home
  ◈  SOP 数据分析   key: sop
  ✦  政策报告撰写   key: policy
  ◉  高级数据分析   key: analytics
  ⬡  数据库连接     key: database
  ◗  个人知识库     key: knowledge
```

**用户信息区（底部）：**
```
padding: 12px 16px
border-top: 1px solid #C4BAA8
layout: flex, alignItems: center, gap: 8px
  - 头像：30×30px, borderRadius: 50%, background: #C8BFB0
  - 用户名：12px Bold
  - 角色：10px color: #9C8E82
  - 更多按钮：marginLeft: auto, "⋯"
```

### 2.3 顶部导航栏规范

```
height: 52px
background: #FEFCF8
border-bottom: 1px solid #C4BAA8
padding: 0 20px
display: flex; alignItems: center; gap: 12px

左侧：面包屑导航
  fontSize: 12px
  各级用 "/" 分隔
  末级颜色：#3D3530（加深）
  其余级别：#9C8E82

右侧工具栏：
  - 通知铃铛按钮：28×28px chip 样式
  - 设置按钮：28×28px chip 样式
  - 用户头像：26×26px 圆形
```

---

## 3. 首页 / 工作台

### 3.1 变体 A — 服务卡片网格

**面包屑：** `工作台 / 首页`

**顶部欢迎区：**
```
layout: flex; justifyContent: space-between; marginBottom: 20px

左侧：
  - 问候语：20px Bold "早上好，张三 👋"
  - 副文字：13px "今天有 N 项任务待处理" color: #9C8E82

右侧按钮组：
  - 次要按钮："查看任务 📋"
  - 主要按钮："新建分析 ＋"（background: #5B8F7A, color: white）
```

**指标卡片行：**
```
layout: flex; gap: 12px; marginBottom: 20px
4 张等宽 MetricCard，内容：
  - 本月分析次数  42   ↑12%（绿色）
  - 生成报告      8    ↑5%（绿色）
  - 知识库文档    126
  - 本周使用时长  18h
```

**服务卡片网格：**
```
display: grid; gridTemplateColumns: repeat(3, 1fr); gap: 14px; flex: 1

每张 ServiceCard：
  background: #FEFCF8; border: 1px solid #C4BAA8; borderRadius: 10px; padding: 14px
  内部布局（column, gap: 10px）：
    1. 顶部行：图标块（42×42px）+ 右侧标签（可选）
    2. 功能名称：14px Bold
    3. 功能描述：11px color: #9C8E82, lineHeight: 1.5
    4. "立即使用 →"：11px Bold, color = 该功能强调色

6 张服务卡片：
  ◈ SOP 数据分析    色: #5B8F7A  标签: 常用
  ✦ 政策报告撰写    色: #C17F3A  标签: 新
  ◉ 高级数据分析    色: #7B6BAA
  ⬡ 数据库连接      色: #3A7FC1
  ◗ 个人知识库      色: #8A6F3A
  +  即将推出        色: #9C8E82
  
图标块：42×42px, borderRadius: 11px
  background: 该色 + "22"（即 13% 透明度，如 #5B8F7A22）
  内含 emoji/符号 20px，颜色 = 该功能强调色
```

### 3.2 变体 B — 仪表盘概览

**面包屑：** `工作台 / 首页 — 仪表盘`

**布局：** 左右两栏 `flex; gap: 16px`

**左栏（flex: 1）：**
```
顶部指标行（flex, gap: 10px）：3 张 MetricCard
  本月分析次数 / 报告生成 / 知识库文档

使用趋势卡片（flex: 1）：
  标题："使用趋势"  右侧操作："切换周期 ▾"
  内容：折线图/柱状图占位区，高度 160px，dashed border

近期任务卡片：
  标题："近期任务"  右侧操作："查看全部"
  列表（3 条，分隔线）：
    - 左侧彩色圆点（7px）
    - 任务名称（flex: 1）
    - 时间戳 color: #9C8E82
    - "继续" Chip 按钮
```

**右栏（width: 256px）：**
```
快速入口卡片：
  标题："快速入口"
  4 条入口（分隔线）：
    图标块(28×28) + 文字 + "→"
  内容：
    ◈ 新建 SOP 分析
    ✦ 撰写政策报告
    ⬡ 连接数据库
    ◗ 上传知识文档

日历卡片（flex: 1）：
  标题："本周日历"
  迷你日历占位（高度 120px）
  今日日程列表（2 条）
```

---

## 4. SOP 数据分析

### 4.1 变体 A — 步骤向导

**面包屑：** `工作台 / SOP 分析 / 新建分析`

**步骤指示器：**
```
layout: flex; alignItems: center; gap: 6px; marginBottom: 20px

4 个 StepBadge + 3 条连接线（Divider）：
  步骤 1 "上传数据"   → 完成状态（background: #D6EDE7, 打勾图标）
  步骤 2 "选择 SOP"   → 激活状态（background: #5B8F7A, 白色文字）
  步骤 3 "配置参数"   → 默认状态
  步骤 4 "生成报告"   → 默认状态

连接线：激活前的线用 accent 色(opacity:0.4)，未激活用 border 色

StepBadge 规范：
  padding: 7px 12px; borderRadius: 8px; display: flex; alignItems: center; gap: 7px
  内圆：20×20px, borderRadius: 50%
    完成：background: #5B8F7A; color: white; 内含 "✓"
    激活：background: white; color: #5B8F7A; 内含数字
    默认：background: #C8BFB0; color: #9C8E82
```

**主体布局（flex, gap: 14px）：**

**左栏 SOP 模板库（width: 272px）：**
```
卡片内：
  搜索框：11px placeholder "🔍 搜索模板…"
  模板列表（5 条）：
    padding: 9px 11px; borderRadius: 8px; marginBottom: 5px
    选中项：background: #5B8F7A; color: white; 右侧"已选"徽章
    未选项：background: pageBg; border: 1px solid border
  模板列表内容：
    销售数据分析 / 财务报表分析（选中）/ 运营指标分析 / 用户行为分析 / 供应链分析
```

**右侧内容区（flex: 1）：**
```
上方：SOP 详情卡片
  标题："财务报表分析 SOP"
  描述文字：11px color: #9C8E82
  功能标签行（水平排列）：
    "收入分析" "成本拆解" "利润率" "同比对比"
    样式：10px; padding: 3px 8px; borderRadius: 10px; background: #D6EDE7; color: #5B8F7A
  预计时间："⏱ 预计分析时间：约 2 分钟"

下方（flex: 1）：数据预览卡片
  标题："已上传数据预览"
  表格列：月份 / 收入(万) / 成本(万) / 净利润 / 增长率
  行数：6 行数据
```

**底部操作栏：**
```
layout: flex; justifyContent: flex-end; gap: 10px; marginTop: 14px
按钮：
  次要："← 上一步"
  主要："开始分析 →"（accent 色）
```

### 4.2 变体 B — 分屏操作台

**面包屑：** `工作台 / SOP 分析`

**工具栏（顶部）：**
```
layout: flex; alignItems: center; gap: 8px; marginBottom: 14px
  - 次要按钮："📤 上传文件"
  - 分隔线（1px 竖线）
  - 文字："当前文件："+ Chip "财务报表_2024Q3.xlsx"
  - 右侧主按钮："▶ 运行分析"
```

**主体分屏（flex, gap: 14px）：**

**左侧数据预览（flex: 1）：**
```
Sheet 标签切换：
  "Sheet1"（激活, accent 色背景）/ "Sheet2" / "Sheet3"
表格：列：日期 / 科目 / 借方 / 贷方 / 余额，9 行数据
```

**右侧 SOP 配置（width: 290px）：**
```
SOP 配置卡片：
  模板下拉选择框："财务报表分析 ▾"
  分析维度复选框（4 个）：
    ✓ 收入趋势（勾选）/ ✓ 成本结构（勾选）/ ✓ 利润分析（勾选）/ ○ 同比环比（未勾）
    勾选框样式：14×14px, borderRadius: 3px
      选中：background: #5B8F7A
      未选：background: chip

分析进度卡片：
  进度条/状态指示占位区，高度 70px

结果摘要卡片（flex: 1）：
  占位区高度 110px："分析完成后自动显示摘要"
  底部按钮行：
    "查看完整报告"（primary, flex: 1）/ "导出"（secondary）
```

---

## 5. 政策报告撰写

### 5.1 变体 A — 文档编辑器

**面包屑：** `工作台 / 政策报告 / 数字经济政策研究报告`

**三栏布局（flex, gap: 14px）：**

**左栏：大纲树（width: 230px）：**
```
卡片内：
  标题："文档大纲"
  大纲项列表：
    缩进规则：每级 +16px paddingLeft（从 8px 开始）
    激活项：background: #D6EDE7; color: #5B8F7A; borderLeft: 2px solid #5B8F7A
    默认项：background: transparent; color: textBody
  
  大纲内容：
    1. 引言（一级）
    2. 背景分析（一级）激活
      2.1 国内形势（二级）
      2.2 国际对比（二级）
    3. 核心政策（一级）
      3.1 产业政策（二级）
      3.2 监管框架（二级）
    4. 建议与展望（一级）
  
  底部："＋ 添加章节" 次要按钮（全宽）
```

**中栏：编辑器（flex: 1）：**
```
工具栏（卡片顶部，独立 div）：
  borderRadius: 10px 10px 0 0（和编辑器主体拼合）
  横向排列 Chip 按钮：B / I / U / 分隔线 / H1 / H2 / 分隔线 / 列表 / 引用 / 分隔线 / 插图 / AI润色
  AI润色 Chip：color: #5B8F7A; background: #D6EDE7

编辑器主体（flex: 1，borderRadius: 0 0 10px 10px）：
  标题："2. 背景分析"（16px Bold）
  正文占位行（5 行，高度 12px，不同宽度百分比）
  子标题："2.1 国内形势"（13px Bold）
  正文占位行（4 行）
  
  AI 建议块：
    background: #D6EDE7; border: 1px solid #5B8F7A; borderRadius: 8px; padding: 10px 12px
    文字：11px color: #5B8F7A "✦ AI 建议：此处可引用……"
    按钮行：
      "采纳"（primary small）/ "忽略"（secondary small）
```

**右栏（width: 210px）：**
```
文档信息卡片：
  键值对列表（分隔线）：
    字数 → 4,280
    章节数 → 8
    状态 → 草稿
    上次保存 → 2分钟前

导出卡片：
  3 个全宽次要按钮：
    "导出 Word (.docx)" / "导出 PDF" / "复制全文 Markdown"

参考资料卡片（flex: 1）：
  列表：
    📎 政策文件数据库
    📎 知识库引用 (3)
    📎 网络资料 (7)
```

### 5.2 变体 B — 引导式流程

**面包屑：** `工作台 / 政策报告 / 新建报告`

**居中内容区（maxWidth: 780px; margin: 0 auto）：**

**步骤指示器：** 同 SOP 变体 A 样式，4 步：
- 主题设定（完成）→ 大纲生成（激活）→ 内容撰写 → 导出保存

**AI 生成大纲卡片：**
```
顶部行：
  标题"AI 生成大纲" + "已完成"徽章（accentLight 底） + "重新生成"次要按钮（右对齐）
副标题：12px color: #9C8E82 "主题：数字经济政策研究报告 · 字数目标：5000 字"

大纲条目（6 条，循环）：
  layout: flex; alignItems: center; gap: 10px
  padding: 9px 12px; borderRadius: 8px; marginBottom: 6px
  background: pageBg; border: 1px solid border
  
  左侧序号圆圈：22×22px; borderRadius: 50%; background: chip; 10px color: textLight
  中间文字（flex: 1）：12px
  右侧 Chip：✎（编辑）/ ☰（拖拽排序）
  
内容：
  一、引言与研究背景
  二、国内外数字经济发展现状
  三、核心政策框架分析
  四、产业影响与机遇研判
  五、政策建议与未来展望
  六、结语

底部操作：
  "＋ 添加章节" 次要 / "调整顺序" 次要
```

**参考资料卡片：**
```
上传拖拽区（180×72px dashed）+ 右侧来源选项：
  ✓ 知识库检索（选中）/ ✓ 政策数据库（选中）/ ○ 网络实时（未选）
```

**底部操作：** `← 返回修改` / `开始撰写内容 →`（primary）

---

## 6. 高级数据分析

### 6.1 变体 A — 图表仪表盘

**面包屑：** `工作台 / 高级数据分析`

**工具栏：**
```
"📂 加载数据集" + Chip"财务数据_2024.xlsx" + 右侧："🔄 刷新" / "📤 导出报告"(primary)
```

**指标行（4 张 MetricCard）：**
数据行数 12,847 / 字段数 24 / 异常值 3% ↓2% / 缺失率 0.8%

**2×2 图表网格（grid, gap: 14px, flex: 1）：**
```
每格：WCard（display: flex; flexDirection: column）
  标题行：功能名 + 右侧"配置图表 ⚙"链接
  图表占位区（flex: 1，minHeight: 120px，dashed）

四格内容：
  左上：收入趋势分析  → 折线图（月度收入趋势 12M）
  右上：成本结构分布  → 环形图（成本构成占比）
  左下：区域销售分布  → 地图热力图
  右下：关键指标相关性 → 散点图矩阵
```

### 6.2 变体 B — 对话驱动分析

**面包屑：** `工作台 / 高级数据分析 / 对话模式`

**布局（flex, gap: 14px）：**

**左侧面板（width: 300px）：**
```
数据源卡片：
  拖拽上传区（76px 高，dashed）
  标签行："数据库" / "知识库"

数据概览卡片（flex: 1）：
  键值列表（分隔线）：
    行数 12,847 / 字段数 24 / 数值列 18 / 文本列 6 / 缺失值 0.8% / 重复行 23
```

**右侧对话结果区（flex: 1）：**
```
分析结果卡片（flex: 1）：
  问题气泡（pageBg底）："❓ 各季度收入对比如何？"
  图表占位（柱状图，高度 120px）
  AI 回答块（accentLight底）：
    "✦ Q3 收入最高达 340 万，同比增长 18%；Q4 环比下降 5%……"
  问题气泡："❓ 成本中哪类占比最大？"
  图表占位（饼图，高度 100px）

底部输入卡片：
  自然语言输入框（flex: 1）+ "分析"按钮（primary）
  快捷标签行：趋势分析 / 异常检测 / 相关性 / 预测建模 / 数据概貌
```

---

## 7. 数据库连接

### 7.1 变体 A — SQL 编辑器

**面包屑：** `工作台 / 数据库连接 / PostgreSQL — 生产库`

**布局（flex, gap: 14px）：**

**左栏：数据库结构树（width: 220px）：**
```
搜索框："🔍 搜索表/字段"
树形列表（accordion）：
  ▶ users
  ▼ orders（展开，激活 bg: chip）
      — id        num
      — user_id   num
      — amount    num
      — status    num
      — created_at num
  ▶ products
  ▶ analytics
```

**右侧（flex: 1）：**
```
SQL 编辑器卡片：
  标题 + 右侧按钮：
    "格式化"（次要 small）/ "▶ 执行"（primary small）
  
  代码区域（monospace font，行高 1.8）：
    background: #F2EDE4; borderRadius: 8px; padding: 12px 14px
    关键字高亮 color: #5B8F7A（accent）
    字符串高亮 color: #C17F3A（amber）
    示例 SQL：
      SELECT o.id, u.name, o.amount, o.status
      FROM orders o JOIN users u ON o.user_id = u.id
      WHERE o.created_at > '2024-01-01'
      ORDER BY o.amount DESC LIMIT 100;
  
  底部工具 Chip：
    "历史查询" / "保存查询" / "AI 优化 SQL"（accent 色）

查询结果卡片（flex: 1）：
  标题行：
    "查询结果" + "共 847 条 · 0.23s"（辅助色）
    右侧：📊 可视化 / 导出 CSV
  
  表格列：ID / 用户名 / 金额 / 状态 / 创建时间，7 行数据
```

### 7.2 变体 B — 可视化查询构建器

**面包屑：** `工作台 / 数据库连接 / 可视化查询构建器`

**布局（flex, gap: 14px）：**

**左栏：数据表列表（width: 190px）：**
```
每张表卡片（可拖拽）：
  background: pageBg; border: 1px solid border; borderRadius: 6px
  layout: flex; gap: 8px; padding: 7px 8px
  图标 ⬡ + 表名 + "拖拽"文字（右侧辅助色）
  cursor: grab

表列表：users / orders / products / analytics / inventory
```

**右侧（flex: 1）：**
```
可视化查询画布卡片（flex: 1）：
  标题："可视化查询画布"
  画布区域：
    background: pageBg; border: 1.5px dashed border; borderRadius: 8px
    居中展示两张表块（JOIN 状态）：
    
    表块 A（users）：
      width: 140px; borderRadius: 8px; overflow: hidden; boxShadow: 0 2px 8px rgba(0,0,0,0.06)
      表头：background: #5B8F7A; padding: 7px 10px; 11px Bold white
      字段行（4个）：id / name / email / created_at，类型"str"
    
    JOIN 连接器（居中）：
      横线（36px, accent 色）
      徽章："JOIN"（10px, accentLight背景, accent 文字）
    
    表块 B（orders）：
      border: 2px solid #C17F3A（amber 强调已选中）
      表头：background: #C17F3A
      字段行（4个）：id / user_id / amount / status，类型"num"
    
    右下角提示：10px color: #9C8E82 "拖拽数据表到画布以建立关联"

底部两栏：
  筛选条件卡片（flex: 1）：
    Chip 行：amount > 1000 / status = 'paid' / "＋ 添加条件"（accent 色）
  
  输出字段卡片（width: 200px）：
    列表：✓ users.name / ✓ orders.amount / ✓ orders.status / ✓ orders.created_at

底部操作：
  "预览 SQL" / "▶ 运行查询"（primary）
```

---

## 8. 个人知识库

### 8.1 变体 A — 文件浏览器

**面包屑：** `工作台 / 个人知识库`

**顶部工具栏：**
```
搜索框（flex: 1）："🔍 语义搜索知识库…"
  background: white; border: 1px solid border; borderRadius: 8px; padding: 7px 12px
按钮："📤 上传文档"（primary）/ "新建文件夹"（次要）
```

**布局（flex, gap: 14px, flex: 1）：**

**左栏：文件夹树（width: 216px）：**
```
卡片内：
  标题："文件夹"
  文件夹列表（5 个）：
    padding: 7px 10px; borderRadius: 8px; marginBottom: 2px
    激活："研究报告"
      background: #D6EDE7; border: 1px solid #5B8F7A
      color: #5B8F7A
    非激活：transparent
    
    每项：📁 图标 + 文件夹名（flex: 1）+ 数量（辅助色）
    
  内容：
    📁 全部文档  126
    📁 政策文件  34
    📁 研究报告  28  ← 激活
    📁 数据资料  45
    📁 参考文献  19
  
  底部标签筛选：
    "重要" / "政策" / "2024" / "待处理"（Chip 样式）
```

**右侧文件网格：**
```
顶部标题行：
  "研究报告" + "28 个文件" + 右侧视图切换："≡ 列表" / "⊞ 网格"（激活，accent 底）

文件网格（3 列，gap: 10px）：
  每张 FileCard：
    background: white; border: 1px solid border; borderRadius: 10px; padding: 14px
    
    文件类型色块（高度 58px）：
      PDF  → background: #FFE8D6; color: #C17F3A; 13px Bold
      XLSX → background: #D6EDE7; color: #5B8F7A
      DOCX → background: #D6E4ED; color: #3A7FC1
    
    文件名：12px Bold; lineHeight: 1.3
    底部行：文件大小（左）/ 日期（右）10px color: textLight

文件列表（6 个）：
  数字经济政策研究报告  PDF   2.4MB  今天
  2024年产业数据分析    XLSX  1.8MB  昨天
  市场调研报告 Q3       DOCX  890KB  3天前
  竞争对手分析框架      PDF   3.1MB  上周
  政策解读与建议汇编    DOCX  540KB  上周
  行业趋势报告 2024     PDF   5.2MB  2周前
```

### 8.2 变体 B — 搜索优先

**面包屑：** `工作台 / 个人知识库 / 搜索`

**居中搜索区（maxWidth: 680px; textAlign: center）：**
```
标题：18px Bold "在知识库中搜索"
副标题：12px "语义搜索 · 关键词检索 · 共 126 个文档"

搜索框：
  border: 2px solid #5B8F7A（强调激活状态）
  borderRadius: 12px; padding: 10px 16px
  内容：🔍 图标 + 输入文字"数字经济政策" + 模式切换 Chip（"语义" / "关键词"）+ "搜索"按钮

历史记录 Chip 行（居中）：
  🕐 政策分析 / 🕐 数据报表 / 🕐 市场研究 / 🕐 竞争对手
```

**主体（flex, gap: 14px）：**

**左侧筛选（width: 196px）：**
```
卡片内：
  文件类型（复选框）：
    ✓ PDF (12) / ✓ Word (8) / ✓ Excel (6) / □ 其他 (2)
  
  时间范围（单选）：
    ○ 最近一周
    ● 最近一月（选中，accent 色）
    ○ 最近半年
    ○ 全部
```

**右侧结果列表：**
```
标题行："找到 28 个结果 · 按相关度排序"（11px 辅助色）

ResultCard（3 条，layout: flex; gap: 12px）：
  左侧文件类型方块：38×38px; borderRadius: 8px
  中间内容（flex: 1）：
    标题行：13px Bold + 相关度徽章（"相关度 98%"，accentLight 底）
    摘要文字：11px lineHeight: 1.5 color: textLight
  右侧操作（flex 列）：
    "查看"（次要 small）/ "引用"（primary small）

3 条结果：
  数字经济政策研究报告  PDF   98%  数字经济政策框架的核心要素包括……
  2024年产业数字化分析  XLSX  87%  数字经济对传统产业的渗透率……
  政策解读：数字中国建设规划  DOCX  82%  到2025年，数字经济核心产业……
```

---

## 9. AI 助理面板

**位置：** 页面最右侧，固定宽度 280px，全高，始终可见

**结构：**

### 9.1 顶部标题栏

```
padding: 14px 16px
border-bottom: 1px solid border
layout: flex; alignItems: center; gap: 8px

内容：
  - 绿色圆点（8×8px, borderRadius: 50%, background: #5B8F7A）
  - "AI 助理"（13px Bold）
  - "Claude" 徽章（marginLeft: auto; fontSize: 10px; background: #D6EDE7; color: #5B8F7A; padding: 2px 8px; borderRadius: 10px）
```

### 9.2 对话区（flex: 1, overflow: hidden）

```
padding: 12px; display: flex; flexDirection: column; gap: 8px

消息气泡：
  AI 消息：
    background: white; border: 1px solid border
    borderRadius: 4px 10px 10px 10px（左上直角，其余圆角）
    padding: 7px 10px; fontSize: 11px; lineHeight: 1.5
    最大宽度 92%; alignSelf: flex-start
  
  用户消息：
    background: #5B8F7A; color: white; border: none
    borderRadius: 10px 4px 10px 10px（右上直角）
    alignSelf: flex-end; 最大宽度 85%

输入中指示（typing）：
  3 个圆点（5×5px, borderRadius: 50%, background: textLight）
  layout: flex; gap: 3px; padding: 2px 6px
  
默认对话内容（用于展示）：
  AI：你好！我是 AI 助理，随时可以帮你分析数据、撰写报告或解答问题。
  用：帮我分析这份数据的关键趋势
  AI：好的，数据显示 Q3 同比增长 18%，华东区域贡献最大，以下是详细分析……
  typing...
```

### 9.3 快捷操作区

```
padding: 8px 12px
border-top: 1px solid border

标签：10px color: textLight "快捷操作"
Chip 行（flexWrap: wrap; gap: 4px）：
  "总结" / "生成报告" / "数据洞察" / "提问"
  样式：10px; padding: 3px 8px; borderRadius: 10px; background: chip; border: 1px solid border
```

### 9.4 输入框

```
padding: 10px 12px

输入区容器：
  background: white; border: 1px solid border; borderRadius: 8px; padding: 7px 10px
  layout: flex; alignItems: center; gap: 6px
  
  - placeholder 文字（flex: 1）："输入问题或指令…" 11px color: textLight
  - 发送按钮：22×22px; borderRadius: 5px; background: #5B8F7A; color: white; "↑"
```

---

## 10. 通用组件规范

### 10.1 卡片 (Card)

```css
background: #FEFCF8;
border: 1px solid #C4BAA8;
border-radius: 10px;
padding: 14px;
```

### 10.2 主要按钮 (Primary Button)

```css
padding: 8px 18px;
border-radius: 8px;
font-size: 12px;
background: #5B8F7A;
color: #ffffff;
border: 1px solid #5B8F7A;
cursor: pointer;
display: inline-flex;
align-items: center;
gap: 5px;
```

### 10.3 次要按钮 (Secondary Button)

```css
/* 同上，替换 */
background: #E5DDD0;
color: #6B5F52;
border-color: #C4BAA8;
```

### 10.4 小尺寸按钮变体

```css
padding: 5px 11px;
font-size: 11px;
/* 其余同父类 */
```

### 10.5 Chip / 标签

```css
padding: 4px 9px;
border-radius: 6px;
background: #E5DDD0;
border: 1px solid #C4BAA8;
font-size: 11px;
color: #6B5F52;
cursor: pointer;
```

### 10.6 指标卡片 (MetricCard)

```
WCard 样式（10px border-radius）
内部（column）：
  label：10px color: textLight; marginBottom: 4px
  value：22px Bold color: textHeading
  delta（可选）：10px; color: accent（正）/ amber（负）; marginTop: 2px; 含 ↑↓ 前缀
```

### 10.7 数据表格 (Table)

```css
border: 1px solid #C4BAA8;
border-radius: 8px;
overflow: hidden;
font-size: 11px;

/* 表头行 */
background: #E5DDD0;
border-bottom: 1px solid #C4BAA8;
padding: 7px 10px per cell;

/* 数据行（斑马纹） */
偶数行：background: #FEFCF8;
奇数行：background: #F7F3EC;
border-bottom: 1px solid #C4BAA8;（最后一行无）
padding: 6px 10px per cell;
```

### 10.8 步骤徽章 (StepBadge)

见第 4.1 节规范。

### 10.9 输入框

```css
background: #F7F3EC;
border: 1px solid #C4BAA8;
border-radius: 6px;
padding: 6px 10px;
font-size: 12px;
color: #6B5F52;

/* 聚焦 */
border-color: #5B8F7A;
box-shadow: 0 0 0 2px rgba(91, 143, 122, 0.25);
```

### 10.10 搜索框

```css
/* 同输入框，额外 */
display: flex;
align-items: center;
gap: 8px;
/* 内含🔍图标前缀 */
placeholder 颜色：#9C8E82
```

---

## 11. 交互与状态管理

### 11.1 全局路由

```
页面导航：点击左侧导航项 → 切换激活项高亮 + 更新主内容区
支持的路由：
  /           → 首页
  /sop        → SOP 分析
  /policy     → 政策报告
  /analytics  → 高级数据分析
  /database   → 数据库连接
  /knowledge  → 个人知识库
```

### 11.2 SOP 分析步骤状态

```
state: currentStep (1-4)
  step 1 → 文件上传界面
  step 2 → SOP 模板选择（线框图展示此步骤）
  step 3 → 参数配置
  step 4 → 报告展示

selectedTemplate：当前选中的 SOP 模板 ID
analysisStatus：idle / running / done / error
```

### 11.3 政策报告流程状态

```
state: reportStep (1-4)
  step 1 → 主题输入
  step 2 → 大纲生成（线框图展示此步骤）
  step 3 → 内容撰写
  step 4 → 导出

outline：Array<{ id, title, order }>（支持拖拽排序）
wordCount：实时字数统计
autoSave：每 30 秒自动保存一次，更新"上次保存"时间戳
```

### 11.4 AI 助理面板

```
messages：Array<{ role: 'ai' | 'user', content: string }>
isTyping：boolean（显示三点动画）
quickActions：根据当前页面动态变化（各页面有专属快捷操作）

面板始终可见，不可折叠
输入框 Enter 发送消息
消息历史随上下文滚动
```

### 11.5 数据库查询

```
activeConnection：当前数据库连接信息
queryText：SQL 编辑器内容
queryResult：{ rows, columns, rowCount, executionTime }
queryStatus：idle / executing / done / error
queryHistory：Array<{ sql, timestamp, rowCount }>
```

### 11.6 知识库

```
currentFolder：当前选中文件夹
searchQuery：搜索关键词
searchMode：'semantic' | 'keyword'
viewMode：'grid' | 'list'
selectedTags：Array<string>（标签筛选）
dateFilter：'week' | 'month' | 'halfYear' | 'all'
```

### 11.7 悬浮状态

```
所有可点击卡片：hover → box-shadow: 0 4px 16px rgba(61, 53, 48, 0.10); cursor: pointer
按钮：hover → opacity: 0.90（主要按钮）/ background 稍深（次要按钮）
导航项：hover → background: rgba(91,143,122,0.10)（非激活项）
Chip：hover → background: #D8D0C2
```

---

## 12. 文件清单

| 文件名               | 说明                               |
|----------------------|------------------------------------|
| `wireframe.html`     | 完整线框图原型（HTML 参考稿）       |
| `README.md`          | 本设计交付文档（即此文件）          |

---

## 快速实现建议

**如果使用 Streamlit（原项目技术栈）：**
- 用 `st.sidebar` 实现左侧导航，配合 `st.session_state["page"]` 控制路由
- 右侧 AI 面板可用 `st.chat_message` + `st.chat_input` 实现
- 卡片用 `st.container()` + 自定义 CSS（`st.markdown("<style>…</style>", unsafe_allow_html=True)`）
- 参考主题色注入到 `.streamlit/config.toml`：
  ```toml
  [theme]
  primaryColor = "#5B8F7A"
  backgroundColor = "#F7F3EC"
  secondaryBackgroundColor = "#EDE7D9"
  textColor = "#3D3530"
  ```

**如果使用 React：**
- 推荐使用 Tailwind CSS 或 CSS Modules 实现令牌系统
- 路由使用 React Router v6
- AI 面板封装为独立组件，通过 Context 共享消息状态
- 表格推荐 TanStack Table；图表推荐 Recharts 或 ECharts

---

*文档版本：v1.0 · 生成于 2026-04-22*
