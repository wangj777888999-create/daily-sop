# 03 · 前端设计系统：Token、Tailwind、Composable 三层

> 本章你将看到的代码：
> - `tailwind.config.js`
> - `src/composables/useDesignTokens.ts`
> - `src/assets/styles/main.css`
> - `docs/规划/ui-design-spec.md`（仓库根目录的设计规范原稿）

---

## 1. 为什么要"设计系统"，而不是直接写颜色

随手翻一眼 `docs/规划/ui-design-spec.md`（顶级设计稿），会发现有很多决策：

- 主背景 `#F7F3EC`（米白）+ 强调色 `#5B8F7A`（鼠尾草绿）。
- 字号有 7 档（title-lg/md/sm + body + helper + label + micro）。
- 间距只有 5 档（xs / sm / md / lg / xl）。
- 圆角只有 4 档（sm / md / lg / xl）。

**这些数值要被"全局共享"**，否则每个组件随手写 `#5B8F7A`，将来改主色就要全局 grep 替换——大型项目第一类技术债。所以本项目走的是**"设计 token 单点定义 → 多种消费方式"** 的标准做法。

```
       ┌────────────────────────────────────────────┐
       │   两份"事实标准"（应保持一致）            │
       │   ▸ tailwind.config.js                    │
       │   ▸ src/composables/useDesignTokens.ts    │
       └─────────┬──────────────────┬──────────────┘
                 │                  │
       ┌─────────▼─────┐     ┌──────▼─────────┐
       │ Tailwind 类名  │     │ 内联 style /    │
       │ bg-accent     │     │ JS 计算颜色     │
       │ text-text-body│     │ getIconBg(...)  │
       └───────────────┘     └────────────────┘
```

> **把 token 抽出来不只是"代码组织"，本质是把"风格"变成可被批量替换的接口**——这一点和后端把"业务规则"提到 model 里是一回事。

---

## 2. 第一层：Tailwind 配置

`tailwind.config.js:9-72` 把所有 token 写进 `theme.extend`：

```javascript
colors: {
  'page-bg': '#F7F3EC',
  'sidebar-bg': '#EDE7D9',
  'card-bg': '#FEFCF8',
  'border': '#C4BAA8',
  'text-heading': '#3D3530',
  'text-body': '#6B5F52',
  'accent': '#5B8F7A',
  'accent-light': '#D6EDE7',
  // ...
},
fontSize: {
  'title-lg': ['20px', { fontWeight: '700', lineHeight: '1.3' }],
  'body':     ['13px', { fontWeight: '400', lineHeight: '1.5' }],
  // ...
},
spacing: { 'xs':'4px', 'sm':'8px', 'md':'12px', 'lg':'14px', 'xl':'20px' },
borderRadius: { 'sm':'6px', 'md':'8px', 'lg':'10px', 'xl':'12px' },
boxShadow: {
  'card': '0 1px 3px rgba(61, 53, 48, 0.07), inset 0 1px 0 rgba(255,255,255,0.75)',
  'card-hover': '0 6px 20px rgba(61, 53, 48, 0.10), 0 1px 4px rgba(61,53,48,0.05)',
  'input-focus': '0 0 0 3px rgba(91, 143, 122, 0.18)',
  // ...
}
```

**注册之后能直接拿 Tailwind 类名用**：

```html
<button class="bg-accent text-card-bg shadow-button-primary rounded-md px-md py-sm">
  保存
</button>
```

注意：

- 颜色名用 kebab-case（`text-text-body` 而不是 `text-textBody`）。
- 字号 token 把 fontWeight + lineHeight 都打包进去——一个类同时给三个属性。
- `xl` 间距是 20px 而不是 Tailwind 默认的 32px——**我们刻意做了紧凑型间距**，配合中文 13px 正文比较协调。

> **"不破坏 token"的纪律**：任何时候你想 `class="text-[#5B8F7A]"` 或 `style="color:#5B8F7A"`，先停下来问"这个值要不要进 token"。绝大多数情况要。

---

## 3. 第二层：composable `useDesignTokens()`

为什么有了 Tailwind 还要 JS 端 token？因为有些场景**只能用 JS 计算**：

- 内联 `style="background: rgba(91, 143, 122, 0.13)"`（图标背景需要带透明度）。
- canvas / chart.js 配置（图表色不能用 class 名）。
- 动态生成颜色（`getIconBg(service.color)`）。

`src/composables/useDesignTokens.ts` 做了两件事：

```typescript
// src/composables/useDesignTokens.ts:60-78
const getColorWithAlpha = (color: string, alpha: number) => {
  const hex = color.replace('#', '')
  const r = parseInt(hex.substring(0, 2), 16)
  // ...
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

return {
  colors, spacing, borderRadius, typography, shadows, layout,
  getColorWithAlpha,
  getIconBg: (color: string) => getColorWithAlpha(color, 0.13)  // 13% 透明度
}
```

调用方式：

```typescript
const { colors, getIconBg } = useDesignTokens()
const iconBg = getIconBg(colors.accent) // → "rgba(91, 143, 122, 0.13)"
```

> **关键风险（已知小缺陷）**：tailwind.config.js 和 useDesignTokens.ts **是手动同步的两份事实**。如果你改了 `accent` 颜色但只改了一处，UI 会不一致。第 12 章把"用脚本生成 useDesignTokens.ts"作为可选改进。

---

## 4. 第三层：组件层的"约定"

约定不是工具，但同样重要。本项目的组件遵守以下约定：

### 4.1 颜色不再写 hex

错误：
```html
<div style="color: #6B5F52">...</div>
```
正确：
```html
<div class="text-text-body">...</div>
```

### 4.2 间距永远走 token

错误：
```html
<div class="px-3 py-2">...</div>
```
正确：
```html
<div class="px-md py-sm">...</div>
```

### 4.3 阴影优先用预设

`shadow-card`、`shadow-card-hover`、`shadow-input-focus`，不要随手 `shadow-md`（Tailwind 默认值与设计稿对不上）。

### 4.4 圆角同理

只用 `rounded-sm/md/lg/xl`，不要 `rounded-2xl`（不在 token 范围内）。

---

## 5. 当前真实状态（截至 2026-04 审计）

| 检查项 | 状态 |
|---|---|
| HomePage、KnowledgePage、PolicyPage 是否守 token | ✅ 基本守 |
| DatabasePage 是否守 token | ⚠️ SQL 编辑器区域有硬编码 `#F2EDE4` |
| AIPanel 是否守 token | ⚠️ 部分使用 hex 字面量（虽然值与 token 一致，但**字面量与 token 是两件事**）|
| `useDesignTokens()` 与 tailwind config 是否完全同步 | ✅ 当前一致 |

> 这些都是**良性技术债**——它们不影响功能，但破坏了"改 token 就能全局换肤"的承诺。修起来的工作量很小，是新手熟悉项目的好题。

---

## 6. 设计风格定调（米白 + 鼠尾草绿）

`docs/规划/ui-design-spec.md` 把这个风格描述为：

> 温暖、内敛、不冷淡。强调"工作面板"而非"科技产品"，避免常见 SaaS 的纯白 + 蓝紫。

具体落到 token：

- **米白 `#F7F3EC` 作页面底色**：比纯白柔和，长时间使用不刺眼。
- **鼠尾草绿 `#5B8F7A` 作 accent**：比常见品牌蓝低饱和、有"工作"质感。
- **textHeading `#3D3530` 而不是黑**：纯黑在米白底上对比过强，深棕更顺眼。

> 设计 token 不只是"工程"，本质是"视觉语言的可执行版本"。理解这一点，读懂任何成熟产品的设计系统都不难。

---

## 动手练习

1. **跑一个 token 一致性检查**：在 `src/` 下用 `rg "#[0-9A-Fa-f]{6}"` 找所有硬编码 hex，统计哪些不在 `useDesignTokens` 里——这就是当前不守 token 的"债务清单"。
2. **加一个新 token**：给 `tailwind.config.js` 和 `useDesignTokens.ts` 都加 `'accent-warm': '#A87E45'`（暖色强调），在某个按钮 hover 用上。
3. **写一个 `tokens.ts` 单源**：尝试只在 TS 文件里定义 token，再用 vite plugin 在构建时生成 tailwind config——你会更深刻地理解"两份配置同步"的麻烦。

## 延伸阅读

- Tailwind 官方 [Theme Configuration](https://tailwindcss.com/docs/theme)：所有 token 类型与默认值。
- 想了解"语义层 vs 原子层" token 划分：Atlassian 的 [Design Tokens](https://atlassian.design/foundations/design-tokens) 写得很清楚。
- 中文阅读体验为什么需要 13px 正文 + 1.5 行高：[Web 中文排印](https://www.thetype.com/2017/05/13658/) 系列。
