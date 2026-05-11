# 02 · 前端 Vue 3 实战

> 本章你将看到的代码：
> - `src/main.ts`、`src/App.vue`、`src/router/index.ts`
> - `src/stores/aiChat.ts`
> - `src/services/sopApi.ts`、`src/services/knowledgeApi.ts`
> - `src/ui/pages/knowledge/KnowledgePage.vue`（作为"标杆页面"参考）

---

## 1. 从 `main.ts` 到一个页面：四步上车

### 1.1 启动入口（13 行就完事）

```typescript
// src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

**对应到熟悉概念**：

- `createApp(App)` ≈ 主入口组件。
- `createPinia()` ≈ 全局状态容器（替代旧 Vuex）。
- `router` ≈ 客户端路由表。
- `main.css` ≈ Tailwind 入口 + 全局样式。

> **关键：`createPinia()` 必须在 `createApp` 之后、`mount` 之前** `use`。Pinia 是基于 `provide/inject` 拿到 app context 的。

### 1.2 路由表 `src/router/index.ts`

12 个路由，全部用懒加载（`() => import(...)`）：

```typescript
// src/router/index.ts:9-14
{
  path: '/home',
  name: 'home',
  component: () => import('@/ui/pages/home/HomePage.vue'),
  meta: { title: '工作台首页' }
}
```

**为什么懒加载？** —— 每个页面打成单独的 chunk，首屏只下载首页代码；点 SOP 才下 SOP chunk。本项目页面多但访问频次低，**这是首屏体感的最大受益点**。

`router.beforeEach` 还做了一件事：把页面 title 写成 `${meta.title} - 智能工作台`（`src/router/index.ts:82-85`）——浏览器标签栏会跟着页面变。

### 1.3 状态管理：Pinia store

最小可工作示例 `src/stores/aiChat.ts`：

```typescript
// src/stores/aiChat.ts
export const useAIChatStore = defineStore('aiChat', {
  state: (): AIChatState => ({
    messages: [],
    isTyping: false,
    quickActions: ['🔍 搜索知识库', '📝 撰写政策', '📊 生成报告'],
  }),
  actions: {
    addMessage(message) { this.messages.push({ ...message, id: Date.now().toString(), timestamp: Date.now() }) },
    setTyping(typing) { this.isTyping = typing },
    clearMessages() { this.messages = [] }
  }
})
```

**这个 store 的设计有几个值得注意的地方**：

1. **没单独写 getters**：派生数据少到不值得专门搞 getter。Vue 偏好"用数据就直接用 state，复杂派生用 `computed`"。
2. **id 用 `Date.now()`**：单用户 + 局部使用足够；如果做多端同步要换 UUID。
3. **`isTyping` 是布尔**：UI 层 `<TypingIndicator v-if="isTyping" />` 一目了然——**简单标志位胜过状态机**。

> ⚠️ 已知改进点：本项目没有"全局 error store"，API 失败时只 console.error。如果你做完 09 章的 RAG 后想统一错误提示，建一个 `useErrorStore` 是合适的下一步。

### 1.4 一个页面的标准结构

挑 `KnowledgePage.vue` 当样板（它是当前完成度最高的页面之一）：

```vue
<template>
  <!-- 1. 顶部工具栏（搜索/筛选） -->
  <!-- 2. 主区：文档列表 / 文件浏览器 -->
  <!-- 3. 右侧抽屉或全屏预览 -->
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { fetchDocuments } from '@/services/knowledgeApi'

const store = useKnowledgeStore()
const selectedDocId = ref<string | null>(null)

onMounted(async () => {
  await Promise.all([fetchDocuments(), store.loadFolders()])
})
</script>
```

> **看这个套路**：`<script setup>` 顶部全是 import + 状态声明 + lifecycle，**把"业务"留给 `template` 上下文里出现的方法和 store**。这是 Vue 3 Composition API 的"好品味"。

---

## 2. 服务层：怎么和后端通信

### 2.1 两种 API 封装风格——并存，但不统一

#### 风格 A：手工 `fetch` + try/catch（`src/services/sopApi.ts`）

```typescript
// src/services/sopApi.ts:46-60
export async function fetchSOPs(): Promise<SOP[]> {
  sopsLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/sops`)
    if (!response.ok) throw new Error('Failed to fetch SOPs')
    const data = await response.json()
    sops.value = data
    return data
  } catch (error) {
    console.error('Error fetching SOPs:', error)
    return []
  } finally {
    sopsLoading.value = false
  }
}
```

**优点**：直观、零依赖。  
**缺点**：每个函数重复一遍 try/catch；错误吞掉只 `console.error`，UI 看不到。

#### 风格 B：通用 `request<T>()` 包装（`src/services/knowledgeApi.ts:13-20`）

```typescript
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
```

**优点**：错误真正向上抛、调用点更短、解析后端 `detail` 字段更友好。  
**缺点**：调用点要自己写 try/catch（不过通常包在 store / page 一层）。

> **决策**：风格 B 是**更应该的做法**。第 12 章的路线图把"sopApi 迁移到 request<T>" 列在 RAG 收尾后立项。学完 09 章 RAG，你可以拿这个改造作为练习。

### 2.2 文件上传：FormData 而不是 JSON

`executeSOP` 在 `sopApi.ts:143-164`：

```typescript
const formData = new FormData()
formData.append('sop_id', sopId)
files.forEach(file => formData.append('files', file))

const response = await fetch(`${API_BASE}/execute/${sopId}`, {
  method: 'POST',
  body: formData
})
```

不要 `headers: 'Content-Type'`——浏览器会自动加 `multipart/form-data; boundary=...`。**手动写反而错**。后端 FastAPI 用 `files: List[UploadFile] = File(...)` 接住，详见第 4 章。

---

## 3. 响应式：`ref` vs `reactive` vs `computed`

### 3.1 模块级共享状态

`sopApi.ts` 在模块顶部直接 `ref([])`：

```typescript
// src/services/sopApi.ts:34-40
export const sops = ref<SOP[]>([])
export const sopsLoading = ref(false)
export const executions = reactive(new Map<string, ExecutionResult>())
```

**模块级 ref 是单例**，在不同组件 import 同一个 ref，会拿到同一份引用。这等价于一个最迷你的 store——本项目里 service 层和 store 之间界限有点模糊（部分原因是历史遗留），但理解这个机制后你可以按需挑：

- 简单 list / loading 状态：用 service 模块级 `ref`。
- 复杂状态机 / 多个 mutation 一起改：用 Pinia store。

### 3.2 `reactive(new Map)` 这个细节

注意 `executions` 用的是 `reactive(new Map(...))` 而不是 `ref<Map<...>>(new Map())`。原因写在源代码注释里（`sopApi.ts:38`）：

```typescript
// Q2: 使用 reactive 而非 ref<Map>，避免 .set() 不触发更新的陷阱
```

**这是一个真实踩过的坑**：`ref(new Map())` 时，`map.value.set(k, v)` 不会触发响应式更新，因为 ref 只追踪 `.value` 的赋值。`reactive(new Map())` 则代理了 Map 上的 `set/get`，set 会触发。

> 第 11 章会讲：**这种"代码注释里写出 Q2 修复" 的做法很值得学**——下次别人（或未来的你）改这块时不会重新踩坑。

---

## 4. 全局 AI 面板（AIPanel.vue）的小心思

`src/ui/components/layout/AIPanel.vue` 是右侧贴边的对话面板：

- 它监听全局 `useAIChatStore`，跟当前路由解耦。
- 当用户问"帮我搜知识库"时，它会调用 `knowledgeApi.searchDocuments()`。
- 当用户在 `PolicyPage` 时，它会带上当前文档 id 作为 RAG 的 `doc_ids`（第 9 章细讲）。

**已知缺口**：目前 AIPanel 不知道用户**当前在看哪个页面 / 哪份文档**——它的"上下文"是固定快捷词。把当前页面 meta + 选中项注入 store，让 AIPanel 真正"上下文感知"，是路线图里 RAG 部分的工作。

---

## 动手练习

1. **熟悉 `<script setup>`**：把任意一个 `*.vue` 页面里的 `<script setup>` 改成 Options API，看 diff——你会更直观感受到 Composition 的简洁。
2. **加一个 quickAction**：在 `aiChat.ts` 的 `quickActions` 加 "📂 搜索文档"，看 AIPanel 自动多一个按钮（好的状态管理就该这样无缝）。
3. **统一错误提示**：建一个 `useErrorStore`，把 `sopApi.ts` 里所有 `console.error` 改为 `errorStore.push(error.message)`，并在 `App.vue` 里加一个全局 toast 容器。

## 延伸阅读

- Vue 官方 [Composition API 介绍](https://cn.vuejs.org/guide/extras/composition-api-faq.html)。
- Pinia 官方文档的 [Defining a Store](https://pinia.vuejs.org/core-concepts/) —— 注意 `state` 必须是 arrow function 返回对象（避免引用泄漏）。
- 想理解"为什么 ref 在 template 里自动 unwrap" 的内部机制：[Reactivity in Depth](https://cn.vuejs.org/guide/extras/reactivity-in-depth.html)。
