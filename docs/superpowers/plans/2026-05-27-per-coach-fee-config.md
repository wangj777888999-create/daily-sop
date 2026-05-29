# Per-Coach Fee Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow each coach to have their own fee rates (football/basketball × package type × on-time/overtime), falling back to a global default when no personal rate is set.

**Architecture:** Extend the existing `fees` structure in `offcampus_fee_rules.json` with a new `coach_fees` dict keyed by coach name. In step 3 of the tool, replace the two global fee tables with a tab-bar UI (one tab per coach + a "全局默认" tab). Backend `_get_fee` checks per-coach rates first, then falls back to `fees`. No new files needed — changes are contained to the Vue component and the Python calculation module.

**Tech Stack:** Vue 3 (Composition API, `ref`, `computed`, `watch`), TypeScript, Tailwind CSS, Python (pandas, FastAPI)

---

## File Map

| File | What changes |
|---|---|
| `src/ui/pages/tools/OffcampusTeachingFee.vue` | Add `coach_fees` state + `currentEditingFees` computed; redesign step-3 template with tab bar |
| `backend/tools/offcampus_teaching_fee.py` | Add `coach_fees: {}` to `DEFAULT_RULES`; update `_get_fee` to check per-coach first |

---

## Task 1: Extend FeeRules type and add per-coach state (script section)

**Files:**
- Modify: `src/ui/pages/tools/OffcampusTeachingFee.vue:8-18` (FeeRules interface)
- Modify: `src/ui/pages/tools/OffcampusTeachingFee.vue:152-165` (state section after editingFees)

- [ ] **Step 1: Replace the `FeeRules` interface**

Find and replace the existing interface (lines 8-19):

```typescript
interface FeeRules {
  sport_keywords: { football: string[]; basketball: string[] }
  package_keywords: {
    football: Record<string, string[]>
    basketball: Record<string, string[]>
  }
  fees: {
    football: Record<string, { 准时: number; 超时: number }>
    basketball: Record<string, { 准时: number; 超时: number }>
  }
  coach_fees?: Record<string, {
    football: Record<string, { 准时: number; 超时: number }>
    basketball: Record<string, { 准时: number; 超时: number }>
  }>
  overtime_threshold_days: number
}
```

- [ ] **Step 2: Add per-coach state refs right after the existing `editingFees` ref (after line ~164)**

The existing block ends with:
```typescript
  },
})
```
(closing of `editingFees` ref). After that block, add:

```typescript
// 当前选中的费率 Tab：'default' 或教练姓名
const activeCoachTab = ref<string>('default')

// 教练个人费率：{ 教练姓名 → { football: {...}, basketball: {...} } }
const editingCoachFees = ref<Record<string, typeof editingFees.value>>({})

/** 当前正在编辑的费率对象（全局默认或某教练的个人费率） */
const currentEditingFees = computed(() => {
  if (activeCoachTab.value === 'default') return editingFees.value
  return editingCoachFees.value[activeCoachTab.value] ?? editingFees.value
})
```

- [ ] **Step 3: Add helper functions after `cancelEdit`**

After the `cancelEdit` function (around line ~190), add:

```typescript
/** 进入费率规则步骤时，为预览数据中每位新教练初始化个人费率（复制当前默认值） */
function initCoachesForStep3() {
  const coaches: string[] = previewData.value?.coaches ?? []
  for (const coach of coaches) {
    if (!editingCoachFees.value[coach]) {
      editingCoachFees.value[coach] = JSON.parse(JSON.stringify(editingFees.value))
    }
  }
  // 如果当前 tab 指向不在本次数据中的教练，重置为默认
  if (activeCoachTab.value !== 'default' && !coaches.includes(activeCoachTab.value)) {
    activeCoachTab.value = 'default'
  }
}

/** 将全局默认费率覆盖写入指定教练 */
function copyDefaultToCoach(coachName: string) {
  editingCoachFees.value[coachName] = JSON.parse(JSON.stringify(editingFees.value))
}

/** 清除教练个人费率（退回使用全局默认） */
function clearCoachFee(coachName: string) {
  delete editingCoachFees.value[coachName]
  activeCoachTab.value = 'default'
}
```

- [ ] **Step 4: Add a watch that calls `initCoachesForStep3` when entering step 3**

Right after the `watch([year, month], ...)` block, add:

```typescript
// 进入费率规则步骤时初始化教练列表
watch(step, (newStep) => {
  if (newStep === 'rules') initCoachesForStep3()
})
```

- [ ] **Step 5: Verify no TypeScript errors**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
npm run type-check
```

Expected: exits 0 (no errors). If errors appear, they will mention missing property types — fix by checking that `editingFees.value` shape matches the type used in the new computed.

---

## Task 2: Load & save `coach_fees` in rules functions

**Files:**
- Modify: `src/ui/pages/tools/OffcampusTeachingFee.vue` — `loadRules` and `saveRulesAndCalculate`

- [ ] **Step 1: Update `loadRules` to populate `editingCoachFees`**

Find the existing `loadRules` function:
```typescript
async function loadRules() {
  try {
    const res = await fetch(`${API}/rules`)
    if (!res.ok) return
    const data: FeeRules = await res.json()
    rules.value = data
    editingFees.value = JSON.parse(JSON.stringify(data.fees))
  } catch {}
}
```

Replace with:
```typescript
async function loadRules() {
  try {
    const res = await fetch(`${API}/rules`)
    if (!res.ok) return
    const data: FeeRules = await res.json()
    rules.value = data
    editingFees.value = JSON.parse(JSON.stringify(data.fees))
    if (data.coach_fees) {
      editingCoachFees.value = JSON.parse(JSON.stringify(data.coach_fees))
    }
  } catch {}
}
```

- [ ] **Step 2: Update `saveRulesAndCalculate` to include `coach_fees`**

Find inside `saveRulesAndCalculate`:
```typescript
    const mergedRules: FeeRules = {
      ...rules.value!,
      fees: editingFees.value,
    }
```

Replace with:
```typescript
    const mergedRules: FeeRules = {
      ...rules.value!,
      fees: editingFees.value,
      coach_fees: editingCoachFees.value,
    }
```

- [ ] **Step 3: Type-check again**

```bash
npm run type-check
```

Expected: 0 errors.

---

## Task 3: Redesign step-3 template — replace two sport cards with tabbed card

**Files:**
- Modify: `src/ui/pages/tools/OffcampusTeachingFee.vue` — template step-3 section

The existing step-3 template has two separate cards:
```
<!-- 足球费率表 --> ... </div>
<!-- 篮球费率表 --> ... </div>
```
They span roughly lines 618–705. Replace **both** cards entirely with this single card:

- [ ] **Step 1: Delete the football card and basketball card, replace with the new combined card**

Remove everything from `<!-- 足球费率表 -->` through the closing `</div>` of `<!-- 篮球费率表 -->`.

Insert in their place:

```vue
      <!-- ── 教练课时费规则（合并足球 + 篮球，按教练 Tab 切换） ── -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">

        <!-- 卡片标题 -->
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">教练课时费规则</h2>
          <span class="text-xs text-text-light">未单独配置的教练使用「全局默认」费率</span>
        </div>

        <!-- Tab 栏 -->
        <div class="flex gap-1.5 px-5 py-2.5 border-b border-border bg-chip/40 overflow-x-auto">
          <!-- 全局默认 tab -->
          <button
            @click="activeCoachTab = 'default'"
            class="px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors flex-shrink-0"
            :class="activeCoachTab === 'default'
              ? 'bg-accent text-white'
              : 'bg-white border border-border text-text-light hover:text-text-heading'"
          >全局默认</button>

          <!-- 每位教练的 tab -->
          <button
            v-for="coach in previewData?.coaches"
            :key="coach"
            @click="activeCoachTab = coach"
            class="px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors flex-shrink-0 flex items-center gap-1"
            :class="activeCoachTab === coach
              ? 'bg-accent text-white'
              : editingCoachFees[coach]
                ? 'bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100'
                : 'bg-white border border-border text-text-light hover:text-text-heading'"
          >
            {{ coach }}
            <span v-if="editingCoachFees[coach]" class="opacity-70 text-[10px]">✎</span>
          </button>
        </div>

        <!-- 教练 tab：操作按钮行 -->
        <div v-if="activeCoachTab !== 'default'" class="flex items-center justify-between px-5 pt-4 pb-0">
          <span class="text-xs text-text-light">
            <template v-if="editingCoachFees[activeCoachTab]">
              已配置个人费率
            </template>
            <template v-else>
              当前使用全局默认费率
            </template>
          </span>
          <div class="flex gap-2">
            <button
              @click="copyDefaultToCoach(activeCoachTab)"
              class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-heading hover:border-accent hover:text-accent transition-colors"
            >复制默认费率</button>
            <button
              v-if="editingCoachFees[activeCoachTab]"
              @click="clearCoachFee(activeCoachTab)"
              class="text-xs px-3 py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
            >清除个人配置</button>
          </div>
        </div>

        <!-- 费率表内容区 -->
        <div class="px-5 pb-5 pt-4 space-y-5">

          <!-- ⚽ 足球 -->
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span>⚽</span>
              <span class="text-xs font-semibold text-text-heading">足球费率</span>
              <span class="text-xs text-text-light">（元 / 课次）</span>
            </div>
            <table class="w-full text-sm border border-border rounded-xl overflow-hidden">
              <thead class="bg-chip">
                <tr>
                  <th class="px-4 py-2 text-left text-text-light font-medium w-44">课包类型</th>
                  <th class="px-4 py-2 text-center text-text-light font-medium">准时</th>
                  <th class="px-4 py-2 text-center text-text-light font-medium">超时</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="pkg in footballPackages"
                  :key="pkg"
                  class="border-t border-border hover:bg-pageBg transition-colors"
                >
                  <td class="px-4 py-2.5 text-text-heading font-medium">{{ pkg }}</td>
                  <td class="px-4 py-2.5 text-center">
                    <input
                      v-model.number="currentEditingFees.football[pkg]['准时']"
                      type="number" min="0"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </td>
                  <td class="px-4 py-2.5 text-center">
                    <input
                      v-model.number="currentEditingFees.football[pkg]['超时']"
                      type="number" min="0"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 🏀 篮球 -->
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span>🏀</span>
              <span class="text-xs font-semibold text-text-heading">篮球费率</span>
              <span class="text-xs text-text-light">（元 / 课次）</span>
            </div>
            <table class="w-full text-sm border border-border rounded-xl overflow-hidden">
              <thead class="bg-chip">
                <tr>
                  <th class="px-4 py-2 text-left text-text-light font-medium w-44">课包类型</th>
                  <th class="px-4 py-2 text-center text-text-light font-medium">准时</th>
                  <th class="px-4 py-2 text-center text-text-light font-medium">超时</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="pkg in basketballPackages"
                  :key="pkg"
                  class="border-t border-border hover:bg-pageBg transition-colors"
                >
                  <td class="px-4 py-2.5 text-text-heading font-medium">{{ pkg }}</td>
                  <td class="px-4 py-2.5 text-center">
                    <input
                      v-model.number="currentEditingFees.basketball[pkg]['准时']"
                      type="number" min="0"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </td>
                  <td class="px-4 py-2.5 text-center">
                    <input
                      v-model.number="currentEditingFees.basketball[pkg]['超时']"
                      type="number" min="0"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>
      </div>
```

- [ ] **Step 2: Also update `footballPackages` and `basketballPackages` computeds to use `currentEditingFees`**

Find (around line ~295):
```typescript
const footballPackages = computed(() => Object.keys(editingFees.value.football))
const basketballPackages = computed(() => Object.keys(editingFees.value.basketball))
```

Replace with:
```typescript
// Package type lists always come from the global default (same keys for all coaches)
const footballPackages = computed(() => Object.keys(editingFees.value.football))
const basketballPackages = computed(() => Object.keys(editingFees.value.basketball))
```

(No actual code change needed here — the package list is intentionally from `editingFees`, not `currentEditingFees`, because all coaches share the same package taxonomy. Leave unchanged.)

- [ ] **Step 3: Type-check and verify frontend builds**

```bash
npm run type-check
```

Expected: 0 errors.

---

## Task 4: Update backend `DEFAULT_RULES` and `_get_fee`

**Files:**
- Modify: `backend/tools/offcampus_teaching_fee.py`

- [ ] **Step 1: Add `coach_fees` key to `DEFAULT_RULES`**

Find in `DEFAULT_RULES`:
```python
    "overtime_threshold_days": 2,
```

Add a line after it (inside the dict):
```python
    "overtime_threshold_days": 2,
    "coach_fees": {},
```

- [ ] **Step 2: Replace `_get_fee` inside `calculate_teaching_fees`**

Find the existing inner function:
```python
    def _get_fee(row: pd.Series) -> float:
        sport = row["_sport"]
        pkg = row["_pkg_type"]
        status = row["_status"]
        try:
            return float(fees_config[sport][pkg][status])
        except (KeyError, TypeError):
            return 0.0
```

Replace with:
```python
    def _get_fee(row: pd.Series) -> float:
        coach = row["_coach"]
        sport = row["_sport"]
        pkg = row["_pkg_type"]
        status = row["_status"]

        # 优先使用教练个人费率
        coach_fees = fees_config.get("coach_fees", {})
        if coach in coach_fees:
            try:
                return float(coach_fees[coach][sport][pkg][status])
            except (KeyError, TypeError):
                pass  # 个人费率缺失该项，落回全局默认

        # 全局默认费率兜底
        try:
            return float(fees_config["fees"][sport][pkg][status])
        except (KeyError, TypeError):
            return 0.0
```

- [ ] **Step 3: Verify Python syntax**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2/backend
source .venv/bin/activate
python -c "from tools.offcampus_teaching_fee import calculate_teaching_fees, DEFAULT_RULES; print('OK'); print('coach_fees key present:', 'coach_fees' in DEFAULT_RULES)"
```

Expected output:
```
OK
coach_fees key present: True
```

---

## Task 5: Final integration check

- [ ] **Step 1: Start dev servers and open the tool**

```bash
# Terminal 1 — backend
cd /Users/wangjun/Desktop/ai_analyst_v2/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8003

# Terminal 2 — frontend
cd /Users/wangjun/Desktop/ai_analyst_v2
npm run dev
```

Open http://localhost:3000, navigate to 工具箱 → 校外课时费计算.

- [ ] **Step 2: Verify step 3 UI renders the tab bar**

After reaching step 3 (or by mocking: click "获取数据预览 →" if DB is available, else temporarily set `step.value = 'rules'` in browser console), confirm:
- "全局默认" tab is visible and active
- Coach tabs appear for each coach in `previewData.coaches`
- Clicking a coach tab switches the fee tables
- "复制默认费率" button appears on coach tabs
- Inputs reflect per-coach values when switching tabs

- [ ] **Step 3: Verify save/load round-trip**

1. Set a non-zero fee for the "全局默认" tab
2. Switch to a coach tab, click "复制默认费率"
3. Change one value for that coach
4. Click "保存规则并计算课时费 →"
5. Open `data/offcampus_fee_rules.json` — confirm `coach_fees` key is present with the coach's custom values
6. Reload the page — confirm values are restored from the file

- [ ] **Step 4: Commit**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
git add src/ui/pages/tools/OffcampusTeachingFee.vue backend/tools/offcampus_teaching_fee.py
git commit -m "feat: 校外课时费支持教练个人费率配置

- 新增 coach_fees 数据结构（每位教练独立费率）
- Step 3 改为 Tab 栏，全局默认 + 每位教练各一 Tab
- 支持「复制默认费率」和「清除个人配置」操作
- 后端 _get_fee 优先使用个人费率，再回落全局默认
- 加载/保存规则时同步持久化 coach_fees

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- ✅ Per-coach fee configuration
- ✅ Falls back to global default for coaches without personal rates
- ✅ Coaches list comes from preview data (step 2)
- ✅ Persisted in `offcampus_fee_rules.json`
- ✅ "复制默认费率" to seed a coach from the default
- ✅ "清除个人配置" to remove override

**Placeholder scan:** No TBDs or vague steps found.

**Type consistency:**
- `editingCoachFees` is `Record<string, typeof editingFees.value>` throughout
- `currentEditingFees` returns `typeof editingFees.value` — the same type used in template `v-model` bindings
- `footballPackages` / `basketballPackages` both key off `editingFees.value` (intentional — package taxonomy is global)
- Backend `coach_fees[coach][sport][pkg][status]` matches the `fees[sport][pkg][status]` shape exactly
