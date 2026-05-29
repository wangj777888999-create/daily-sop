<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import Button from '@/ui/components/common/Button.vue'

// ── 类型定义 ──────────────────────────────────────────────────
type Step = 'setup' | 'preview' | 'new_classes' | 'capacity' | 'rules' | 'result'

type CoachFeeTable = {
  football: Record<string, { 准时: number; 超时: number }>
  basketball: Record<string, { 准时: number; 超时: number }>
}

interface CourseMapping {
  sport: 'football' | 'basketball' | 'unknown'
  pkg_type: string
}

interface AttendanceTier {
  min: number        // 0.0 – 1.0，如 0.9 表示 ≥90%
  football: number   // 元/人次
  basketball: number
}

interface SpecialFees {
  yuedong_per_session: number  // 跃动课包固定单价
  one_on_one_rate: number      // 一对一私教比率（如 0.12 = 12%）
}

interface NewClass {
  id: string
  course_name: string
  start_date: string  // YYYY-MM-DD
  end_date: string    // 自动 = start_date + 57 天
}

interface FeeRules {
  sport_keywords: { football: string[]; basketball: string[] }
  package_keywords: { football: Record<string, string[]>; basketball: Record<string, string[]> }
  fees: CoachFeeTable
  coach_fees?: Record<string, CoachFeeTable>
  course_pack_mapping?: Record<string, CourseMapping>
  attendance_tiers: AttendanceTier[]
  special_fees: SpecialFees
  overtime_threshold_days: number
}

// ── LocalStorage Key ──────────────────────────────────────────
const SQL_STORAGE_CLASS   = 'offcampus_class_sql'
const SQL_STORAGE_FINANCE = 'offcampus_finance_sql'
const NEW_CLASS_STORAGE   = 'offcampus_new_class_rules'

// ── 月份工具 ──────────────────────────────────────────────────
function monthStr(y: number, m: number) {
  return `${y}-${String(m).padStart(2, '0')}`
}
function getLastDay(y: number, m: number): string {
  const last = new Date(y, m, 0).getDate()
  return `${monthStr(y, m)}-${String(last).padStart(2, '0')}`
}
function replaceSqlMonth(sql: string, y: number, m: number): string {
  const ms = monthStr(y, m)
  let result = sql.replace(/'(\d{4}-\d{2})'/g, `'${ms}'`)
  result = result.replace(
    /BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'/gi,
    `BETWEEN '${ms}-01' AND '${getLastDay(y, m)}'`,
  )
  return result
}

// ── 新开班日期工具 ─────────────────────────────────────────────
function computeEndDate(startDate: string): string {
  if (!startDate) return ''
  const d = new Date(startDate)
  d.setDate(d.getDate() + 57)
  return d.toISOString().slice(0, 10)
}

// ── 状态 ──────────────────────────────────────────────────────
const step    = ref<Step>('setup')
const loading = ref(false)
const errorMsg = ref('')
const saveSuccessMsg = ref('')

const year  = ref(new Date().getMonth() === 0 ? new Date().getFullYear() - 1 : new Date().getFullYear())
const month = ref(new Date().getMonth() === 0 ? 12 : new Date().getMonth())

// ── SQL（从 localStorage 加载，无默认值）────────────────────────
const classSql   = ref(localStorage.getItem(SQL_STORAGE_CLASS)   ?? '')
const financeSql = ref(localStorage.getItem(SQL_STORAGE_FINANCE) ?? '')

// SQL 编辑状态
const classSqlEditing   = ref(false)
const financeSqlEditing = ref(false)
const classSqlDraft     = ref(classSql.value)
const financeSqlDraft   = ref(financeSql.value)

function openEdit(type: 'class' | 'finance') {
  if (type === 'class') { classSqlDraft.value = classSql.value; classSqlEditing.value = true }
  else { financeSqlDraft.value = financeSql.value; financeSqlEditing.value = true }
}
function saveEdit(type: 'class' | 'finance') {
  if (type === 'class') {
    classSql.value = classSqlDraft.value
    classSqlEditing.value = false
    localStorage.setItem(SQL_STORAGE_CLASS, classSql.value)
  } else {
    financeSql.value = financeSqlDraft.value
    financeSqlEditing.value = false
    localStorage.setItem(SQL_STORAGE_FINANCE, financeSql.value)
  }
}
function cancelEdit(type: 'class' | 'finance') {
  if (type === 'class') classSqlEditing.value = false
  else financeSqlEditing.value = false
}

// ── 数据预览 ──────────────────────────────────────────────────
const previewData = ref<any>(null)
const rules       = ref<FeeRules | null>(null)
const result      = ref<any>(null)
const downloadFilename = ref('')

// ── 新开班配置 + 排除关键词 ───────────────────────────────────
const newClasses        = ref<NewClass[]>([])
const newClassInput     = ref({ course_name: '', start_date: '' })
const exclusionKeywords = ref<string[]>(['假期'])
const newKeywordInput   = ref('')
const exclusionDates    = ref<string[]>([])
const newDateInput      = ref('')

function loadNewClassesFromStorage() {
  try {
    const d = JSON.parse(localStorage.getItem(NEW_CLASS_STORAGE) || '{}')
    newClasses.value        = d.new_classes        ?? []
    exclusionKeywords.value = d.exclusion_keywords ?? ['假期']
    exclusionDates.value    = d.exclusion_dates    ?? []
    classCapacity.value     = d.class_capacity     ?? {}
  } catch {
    newClasses.value        = []
    exclusionKeywords.value = ['假期']
    exclusionDates.value    = []
    classCapacity.value     = {}
  }
}

function saveNewClassesToStorage() {
  localStorage.setItem(NEW_CLASS_STORAGE, JSON.stringify({
    new_classes:        newClasses.value,
    exclusion_keywords: exclusionKeywords.value,
    exclusion_dates:    exclusionDates.value,
    class_capacity:     classCapacity.value,
  }))
}

function addExclusionKeyword() {
  const kw = newKeywordInput.value.trim()
  if (!kw || exclusionKeywords.value.includes(kw)) return
  exclusionKeywords.value.push(kw)
  newKeywordInput.value = ''
  saveNewClassesToStorage()
}

function removeExclusionKeyword(kw: string) {
  exclusionKeywords.value = exclusionKeywords.value.filter(k => k !== kw)
  saveNewClassesToStorage()
}

function addExclusionDate() {
  const d = newDateInput.value.trim()
  if (!d || exclusionDates.value.includes(d)) return
  exclusionDates.value = [...exclusionDates.value, d].sort()
  newDateInput.value = ''
  saveNewClassesToStorage()
}

function removeExclusionDate(d: string) {
  exclusionDates.value = exclusionDates.value.filter(x => x !== d)
  saveNewClassesToStorage()
}

// ── 班级应到人数配置 ──────────────────────────────────────────
const classCapacity       = ref<Record<string, number>>({})
const showCapacityImport  = ref(false)
const capacityImportText  = ref('')
const capacityImportError = ref('')

function parseCapacityText(text: string): Record<string, number> {
  const result: Record<string, number> = {}
  for (const line of text.trim().split('\n')) {
    // 支持 Tab 分隔（Excel 复制）或空白分隔
    const parts = line.split(/\t|  +/).map(s => s.trim()).filter(Boolean)
    if (parts.length < 2) continue
    const name = parts[0]
    const num  = parseInt(parts[parts.length - 1], 10)   // 取最后一列为数字
    if (!name || isNaN(num) || num <= 0) continue
    result[name] = num
  }
  return result
}

function applyCapacityImportText() {
  capacityImportError.value = ''
  const parsed = parseCapacityText(capacityImportText.value)
  const count  = Object.keys(parsed).length
  if (count === 0) {
    capacityImportError.value = '未解析到有效数据，请确认格式：每行「课程名称<Tab>人数」（从 Excel 直接复制两列即可）'
    return
  }
  Object.assign(classCapacity.value, parsed)
  saveNewClassesToStorage()
  capacityImportText.value  = ''
  showCapacityImport.value  = false
  showSaveSuccess(`已导入 ${count} 条应到人数配置`)
}

function handleCapacityFileImport(event: Event) {
  capacityImportError.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data    = JSON.parse(e.target?.result as string)
      // 支持完整导出 JSON（含 class_capacity 字段）或纯字典
      const capacity: Record<string, number> = data.class_capacity ?? data
      if (typeof capacity !== 'object' || Array.isArray(capacity)) throw new Error()
      const count = Object.keys(capacity).filter(k => capacity[k] > 0).length
      Object.assign(classCapacity.value, capacity)
      saveNewClassesToStorage()
      showCapacityImport.value = false
      showSaveSuccess(`已从文件导入 ${count} 条应到人数配置`)
    } catch {
      capacityImportError.value = '文件解析失败，请确认为正确的 JSON 格式'
    }
  }
  reader.readAsText(file)
  ;(event.target as HTMLInputElement).value = ''
}

function initClassCapacity() {
  const allCourses: string[] = previewData.value?.all_course_names ?? []
  for (const cn of allCourses) {
    if (!(cn in classCapacity.value)) classCapacity.value[cn] = 0
  }
}

// 过滤掉已被关键词排除、新开班排除的课程，只展示需要计算到课率的班级
const sortedCapacityCourses = computed(() => {
  const newClassNames = new Set(newClasses.value.map(nc => nc.course_name))
  return Object.keys(classCapacity.value)
    .filter(cn =>
      !exclusionKeywords.value.some(kw => kw && cn.includes(kw)) &&
      !newClassNames.has(cn)
    )
    .sort((a, b) => {
      const aOk = (classCapacity.value[a] ?? 0) > 0
      const bOk = (classCapacity.value[b] ?? 0) > 0
      if (aOk !== bOk) return aOk ? 1 : -1   // 未配置的排前面
      return a.localeCompare(b, 'zh')
    })
})

const unconfiguredCapacityCount = computed(() =>
  sortedCapacityCourses.value.filter(cn => !(classCapacity.value[cn] > 0)).length
)

function addNewClass() {
  const name = newClassInput.value.course_name.trim()
  const sd   = newClassInput.value.start_date
  if (!name || !sd) return
  newClasses.value.push({
    id: Date.now().toString(),
    course_name: name,
    start_date: sd,
    end_date: computeEndDate(sd),
  })
  newClassInput.value = { course_name: '', start_date: '' }
  saveNewClassesToStorage()
}

function removeNewClass(id: string) {
  newClasses.value = newClasses.value.filter(nc => nc.id !== id)
  saveNewClassesToStorage()
}

const API = '/api/tools/offcampus-teaching-fee'

async function saveNewClassRules() {
  loading.value = true
  errorMsg.value = ''
  try {
    const body = { new_classes: newClasses.value, exclusion_keywords: exclusionKeywords.value, exclusion_dates: exclusionDates.value, class_capacity: classCapacity.value }
    const res = await fetch(`${API}/new-class-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error('保存失败')
    saveNewClassesToStorage()
    showSaveSuccess('排除配置已保存')
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function exportNewClassRules() {
  const payload = { new_classes: newClasses.value, exclusion_keywords: exclusionKeywords.value, exclusion_dates: exclusionDates.value, class_capacity: classCapacity.value }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `新开班配置_${year.value}-${String(month.value).padStart(2, '0')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── 到课率阶梯 + 特殊费率（编辑暂存）────────────────────────────
const DEFAULT_TIERS: AttendanceTier[] = [
  { min: 0.9, football: 18, basketball: 17 },
  { min: 0.8, football: 17, basketball: 16 },
  { min: 0.7, football: 16, basketball: 15 },
  { min: 0.5, football: 10, basketball: 10 },
  { min: 0.0, football:  5, basketball:  5 },
]
const DEFAULT_SPECIAL: SpecialFees = { yuedong_per_session: 10, one_on_one_rate: 0.12 }

const editingTiers       = ref<AttendanceTier[]>(JSON.parse(JSON.stringify(DEFAULT_TIERS)))
const editingSpecialFees = ref<SpecialFees>({ ...DEFAULT_SPECIAL })

function tierLabel(index: number): string {
  const t    = editingTiers.value[index]
  const next = editingTiers.value[index - 1]
  if (index === 0) return `≥ ${(t.min * 100).toFixed(0)}%`
  if (index === editingTiers.value.length - 1) return `< ${(next.min * 100).toFixed(0)}%`
  return `${(t.min * 100).toFixed(0)}% – ${(next.min * 100).toFixed(0)}%`
}

// ── 教练个人费率（tab 区域保留，供特殊场景覆盖）────────────────
const editingFees = ref<CoachFeeTable>({
  football:   { 正常课包: { 准时: 0, 超时: 0 }, 跃动课包: { 准时: 0, 超时: 0 }, '168拼团课包': { 准时: 0, 超时: 0 } },
  basketball: { 正常课包: { 准时: 0, 超时: 0 }, '168课包': { 准时: 0, 超时: 0 }, 一对一私教: { 准时: 0, 超时: 0 } },
})
const editingCoachFees = ref<Record<string, CoachFeeTable>>({})
const activeCoachTab   = ref<string>('default')

const currentEditingFees = computed(() => {
  if (activeCoachTab.value === 'default') return editingFees.value
  return editingCoachFees.value[activeCoachTab.value] ?? editingFees.value
})

function initCoachFees() {
  const coaches: string[] = previewData.value?.coaches ?? []
  for (const coach of coaches) {
    if (!editingCoachFees.value[coach]) {
      editingCoachFees.value[coach] = JSON.parse(JSON.stringify(editingFees.value))
    }
  }
  if (activeCoachTab.value !== 'default' && !coaches.includes(activeCoachTab.value)) {
    activeCoachTab.value = 'default'
  }
}

function copyDefaultToCoach(coachName: string) {
  editingCoachFees.value[coachName] = JSON.parse(JSON.stringify(editingFees.value))
}

function clearCoachFee(coachName: string) {
  delete editingCoachFees.value[coachName]
  activeCoachTab.value = 'default'
}

// ── 课包分类映射 ───────────────────────────────────────────────
const editingCoursePackMapping = ref<Record<string, CourseMapping>>({})

function initCourseMapping() {
  const allPacks: string[] = previewData.value?.all_course_packs ?? []
  if (!rules.value) return
  for (const pack of allPacks) {
    if (editingCoursePackMapping.value[pack]) continue
    let sport: CourseMapping['sport'] = 'unknown'
    if (rules.value.sport_keywords.football.some((kw: string) => pack.includes(kw)))       sport = 'football'
    else if (rules.value.sport_keywords.basketball.some((kw: string) => pack.includes(kw))) sport = 'basketball'
    editingCoursePackMapping.value[pack] = {
      sport,
      pkg_type: sport === 'basketball' ? basketballPackages.value[0] ?? '正常课包'
                                       : footballPackages.value[0]  ?? '正常课包',
    }
  }
}

function onCourseSportChange(pack: string) {
  const sport = editingCoursePackMapping.value[pack]?.sport
  const pkgs  = sport === 'football' ? footballPackages.value
              : sport === 'basketball' ? basketballPackages.value : []
  if (editingCoursePackMapping.value[pack])
    editingCoursePackMapping.value[pack].pkg_type = pkgs[0] ?? '正常课包'
}

function pkgOptionsForSport(sport: string) {
  if (sport === 'football')   return footballPackages.value
  if (sport === 'basketball') return basketballPackages.value
  return []
}

const unknownSportCount = computed(() =>
  Object.values(editingCoursePackMapping.value).filter(m => m.sport === 'unknown').length
)

// ── 选项 ──────────────────────────────────────────────────────
const monthOptions = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }))
const yearOptions  = [2024, 2025, 2026, 2027].map(y => ({ value: y, label: `${y}年` }))

const footballPackages   = computed(() => Object.keys(editingFees.value.football))
const basketballPackages = computed(() => Object.keys(editingFees.value.basketball))

// ── 步骤指示器 ────────────────────────────────────────────────
const steps = [
  { key: 'setup',       label: '配置 SQL'   },
  { key: 'preview',     label: '数据预览'   },
  { key: 'new_classes', label: '排除配置'   },
  { key: 'capacity',    label: '应到人数'   },
  { key: 'rules',       label: '费率规则'   },
  { key: 'result',      label: '计算结果'   },
] as const
const stepOrder = ['setup', 'preview', 'new_classes', 'capacity', 'rules', 'result']
function stepDone(key: string)   { return stepOrder.indexOf(step.value) > stepOrder.indexOf(key) }
function stepActive(key: string) { return step.value === key }

// ── Watch ─────────────────────────────────────────────────────
watch(step, (newStep) => {
  if (newStep === 'rules') {
    initCoachFees()
    initCourseMapping()
  }
  if (newStep === 'capacity') {
    initClassCapacity()
  }
})

watch([year, month], ([y, m]) => {
  if (classSql.value) {
    classSql.value = replaceSqlMonth(classSql.value, y, m)
    localStorage.setItem(SQL_STORAGE_CLASS, classSql.value)
  }
  if (classSqlEditing.value) classSqlDraft.value = replaceSqlMonth(classSqlDraft.value, y, m)
  if (financeSql.value) {
    financeSql.value = replaceSqlMonth(financeSql.value, y, m)
    localStorage.setItem(SQL_STORAGE_FINANCE, financeSql.value)
  }
  if (financeSqlEditing.value) financeSqlDraft.value = replaceSqlMonth(financeSqlDraft.value, y, m)
})

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  loadRules()
  loadNewClassesFromStorage()
})

async function loadRules() {
  try {
    const res = await fetch(`${API}/rules`)
    if (!res.ok) return
    const data: FeeRules = await res.json()
    rules.value = data
    editingFees.value = JSON.parse(JSON.stringify(data.fees))
    if (data.coach_fees)         editingCoachFees.value         = JSON.parse(JSON.stringify(data.coach_fees))
    if (data.course_pack_mapping) editingCoursePackMapping.value = JSON.parse(JSON.stringify(data.course_pack_mapping))
    if (data.attendance_tiers?.length) editingTiers.value       = JSON.parse(JSON.stringify(data.attendance_tiers))
    if (data.special_fees)        editingSpecialFees.value      = { ...DEFAULT_SPECIAL, ...data.special_fees }
  } catch {}
}

// ── 步骤一：获取数据预览 ──────────────────────────────────────
async function fetchData() {
  if (!classSql.value.trim()) {
    errorMsg.value = '上课记录 SQL 不能为空，请点击「编辑」配置'
    classSqlEditing.value = true
    return
  }
  if (!financeSql.value.trim()) {
    errorMsg.value = '财务明细 SQL 不能为空，请点击「+ 配置 SQL」'
    financeSqlEditing.value = true
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`${API}/fetch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_sql: classSql.value, finance_sql: financeSql.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '获取数据失败')
    previewData.value = data
    step.value = 'preview'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

// ── 工具：显示保存成功提示 ────────────────────────────────────
function showSaveSuccess(msg: string) {
  saveSuccessMsg.value = msg
  setTimeout(() => saveSuccessMsg.value = '', 2500)
}

// ── 规则构建 ──────────────────────────────────────────────────
function buildMergedRules(): FeeRules {
  return {
    ...rules.value!,
    fees:               editingFees.value,
    coach_fees:         editingCoachFees.value,
    course_pack_mapping: editingCoursePackMapping.value,
    attendance_tiers:   editingTiers.value,
    special_fees:       editingSpecialFees.value,
  }
}

// ── 步骤三：保存规则并计算 ────────────────────────────────────
async function saveRulesAndCalculate() {
  loading.value = true
  errorMsg.value = ''
  try {
    const mergedRules = buildMergedRules()
    await fetch(`${API}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mergedRules),
    })
    rules.value = mergedRules

    const res = await fetch(`${API}/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        class_sql:       classSql.value,
        finance_sql:     financeSql.value,
        rules:           mergedRules,
        new_class_config: { new_classes: newClasses.value, exclusion_keywords: exclusionKeywords.value, exclusion_dates: exclusionDates.value, class_capacity: classCapacity.value },
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '计算失败')
    result.value = data
    downloadFilename.value = data.filename || ''
    step.value = 'result'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function saveRulesOnly() {
  if (!rules.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const merged = buildMergedRules()
    const res = await fetch(`${API}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(merged),
    })
    if (!res.ok) throw new Error('暂存失败')
    rules.value = merged
    showSaveSuccess('规则已暂存')
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function exportRules() {
  const merged = buildMergedRules()
  const blob = new Blob([JSON.stringify(merged, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `课时费规则_${year.value}-${String(month.value).padStart(2, '0')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadExcel() {
  if (!downloadFilename.value) return
  window.open(`${API}/download/${encodeURIComponent(downloadFilename.value)}`, '_blank')
}

function reset() {
  step.value = 'setup'
  previewData.value = null
  result.value = null
  errorMsg.value = ''
}

// ── 全量数据分页查看 ──────────────────────────────────────────
const fullDataVisible  = ref(false)
const fullDataTable    = ref<'class' | 'finance'>('class')
const fullDataSearch   = ref('')
const fullDataPage     = ref(1)
const fullDataPageSize = 50
const fullDataLoading  = ref(false)
const fullDataResult   = ref<{
  columns: string[]; rows: string[][]; total: number; total_pages: number
} | null>(null)

let _searchTimer: ReturnType<typeof setTimeout> | null = null

async function fetchFullData() {
  if (!classSql.value || !financeSql.value) return
  fullDataLoading.value = true
  try {
    const res = await fetch(`${API}/fetch-page`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        class_sql:   classSql.value,
        finance_sql: financeSql.value,
        table:       fullDataTable.value,
        page:        fullDataPage.value,
        page_size:   fullDataPageSize,
        search:      fullDataSearch.value,
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '查询失败')
    fullDataResult.value = data
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    fullDataLoading.value = false
  }
}

watch(fullDataTable, () => {
  fullDataPage.value = 1
  fullDataResult.value = null
  if (fullDataVisible.value) fetchFullData()
})

watch(fullDataSearch, () => {
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    fullDataPage.value = 1
    if (fullDataVisible.value) fetchFullData()
  }, 400)
})

function toggleFullData() {
  fullDataVisible.value = !fullDataVisible.value
  if (fullDataVisible.value && !fullDataResult.value) fetchFullData()
}

function goFullDataPage(p: number) {
  if (!fullDataResult.value) return
  const total = fullDataResult.value.total_pages
  fullDataPage.value = Math.max(1, Math.min(p, total))
  fetchFullData()
}

// ── 计算结果数据 ──────────────────────────────────────────────
const coachResults          = computed(() => (result.value?.coach_results ?? []) as any[])
const stats                 = computed(() => result.value?.stats || {})
const overtimeDetailVisible = ref(false)
const grandTotal   = computed(() =>
  coachResults.value.reduce((s: number, r: any) => s + (r.total ?? 0), 0)
)
</script>

<template>
  <div class="min-h-screen bg-pageBg p-6 space-y-6">

    <!-- 标题栏 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-text-heading">校外课时费计算</h1>
        <p class="text-sm text-text-light mt-0.5">从数据库拉取上课记录与财务明细，按到课率阶梯自动计算教练课时费</p>
      </div>
      <Button v-if="step !== 'setup'" variant="secondary" size="small" @click="reset">重新开始</Button>
    </div>

    <!-- 步骤指示器 -->
    <div class="flex items-center gap-0">
      <template v-for="(s, idx) in steps" :key="s.key">
        <div class="flex items-center gap-2">
          <div
            class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors"
            :class="stepDone(s.key)   ? 'bg-accent text-white'
                  : stepActive(s.key) ? 'bg-accent text-white ring-2 ring-accent/30'
                  :                     'bg-chip text-text-light'"
          >
            <span v-if="stepDone(s.key)">✓</span>
            <span v-else>{{ idx + 1 }}</span>
          </div>
          <span class="text-sm" :class="stepActive(s.key) ? 'text-text-heading font-medium' : 'text-text-light'">
            {{ s.label }}
          </span>
        </div>
        <div v-if="idx < steps.length - 1" class="flex-1 h-px bg-border mx-3 min-w-[20px]" />
      </template>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="rounded-xl bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm flex items-start gap-2">
      <span class="mt-0.5">⚠️</span><span>{{ errorMsg }}</span>
    </div>

    <!-- ── Step 1: 配置 SQL ── -->
    <div v-if="step === 'setup'" class="space-y-5">

      <!-- 月份选择 -->
      <div class="bg-white rounded-2xl border border-border p-5 space-y-3">
        <h2 class="text-sm font-semibold text-text-heading">选择月份</h2>
        <div class="flex gap-3">
          <select v-model="year"
            class="rounded-lg border border-border bg-pageBg px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent">
            <option v-for="y in yearOptions" :key="y.value" :value="y.value">{{ y.label }}</option>
          </select>
          <select v-model="month"
            class="rounded-lg border border-border bg-pageBg px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent">
            <option v-for="m in monthOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
          <span class="self-center text-xs text-text-light">切换月份后 SQL 中的日期自动同步</span>
        </div>
      </div>

      <!-- 上课记录 SQL -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3.5" :class="classSqlEditing ? 'border-b border-border' : ''">
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="text-xs font-semibold text-white bg-accent px-2 py-0.5 rounded-full flex-shrink-0">上课记录</span>
            <h2 class="text-sm font-semibold text-text-heading flex-shrink-0">上课记录 SQL</h2>
            <span v-if="!classSqlEditing && classSql.trim()" class="text-xs text-text-light truncate hidden sm:block">
              · 查询 {{ year }}-{{ String(month).padStart(2,'0') }} 月数据
            </span>
            <span v-if="!classSqlEditing && !classSql.trim()" class="text-xs text-amber-600 font-medium">· 尚未配置</span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 ml-3">
            <template v-if="!classSqlEditing">
              <button @click="openEdit('class')"
                class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-heading hover:border-accent hover:text-accent transition-colors">
                {{ classSql.trim() ? '编辑' : '+ 配置 SQL' }}
              </button>
            </template>
            <template v-else>
              <button @click="cancelEdit('class')"
                class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-light hover:text-text-heading transition-colors">取消</button>
              <button @click="saveEdit('class')"
                class="text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors font-medium">保存</button>
            </template>
          </div>
        </div>
        <div v-if="classSqlEditing" class="p-5 space-y-3">
          <p class="text-xs text-text-light">
            需包含：<code class="bg-chip px-1 rounded">课程名称</code>
            <code class="bg-chip px-1 rounded mx-1">课程信息</code>（格式 <code class="bg-chip px-1 rounded">2026-04-01 09:00-10:00</code>）
            <code class="bg-chip px-1 rounded mx-1">状态</code>（已到/请假/旷课…）
            <code class="bg-chip px-1 rounded mx-1">创建时间</code>
            <code class="bg-chip px-1 rounded text-amber-600 border border-amber-200">会员姓名</code>
            <span class="text-amber-600 ml-0.5">← 超时按学员精确匹配必需</span>
          </p>
          <textarea v-model="classSqlDraft" rows="14"
            class="w-full rounded-xl border border-border bg-pageBg px-4 py-3 text-sm font-mono text-text-heading focus:outline-none focus:ring-1 focus:ring-accent resize-y" />
        </div>
      </div>

      <!-- 财务明细 SQL -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3.5" :class="financeSqlEditing ? 'border-b border-border' : ''">
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="text-xs font-semibold text-white bg-[#2563EB] px-2 py-0.5 rounded-full flex-shrink-0">财务明细</span>
            <h2 class="text-sm font-semibold text-text-heading flex-shrink-0">财务明细 SQL</h2>
            <span v-if="!financeSqlEditing && financeSql.trim()" class="text-xs text-text-light truncate hidden sm:block">
              · 查询 {{ year }}-{{ String(month).padStart(2,'0') }} 月数据
            </span>
            <span v-if="!financeSqlEditing && !financeSql.trim()" class="text-xs text-amber-600 font-medium">· 尚未配置</span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 ml-3">
            <template v-if="!financeSqlEditing">
              <button @click="openEdit('finance')"
                class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-heading hover:border-accent hover:text-accent transition-colors">
                {{ financeSql.trim() ? '编辑' : '+ 配置 SQL' }}
              </button>
            </template>
            <template v-else>
              <button @click="cancelEdit('finance')"
                class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-light hover:text-text-heading transition-colors">取消</button>
              <button @click="saveEdit('finance')"
                class="text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors font-medium">保存</button>
            </template>
          </div>
        </div>
        <div v-if="financeSqlEditing" class="p-5 space-y-3">
          <p class="text-xs text-text-light">
            需包含：<code class="bg-chip px-1 rounded">course_name</code>
            <code class="bg-chip px-1 rounded mx-1">class_date</code>
            <code class="bg-chip px-1 rounded mx-1">coach_name</code>
            <code class="bg-chip px-1 rounded mx-1">订单类型</code>（校区）
            <code class="bg-chip px-1 rounded mx-1">course_pack_name</code>
            <code class="bg-chip px-1 rounded">unit_price</code>
          </p>
          <textarea v-model="financeSqlDraft" rows="10"
            placeholder="SELECT ... FROM 财务明细表 WHERE ..."
            class="w-full rounded-xl border border-border bg-pageBg px-4 py-3 text-sm font-mono text-text-heading placeholder-text-light focus:outline-none focus:ring-1 focus:ring-accent resize-y" />
        </div>
      </div>

      <div class="flex justify-end">
        <Button :disabled="loading" @click="fetchData">
          {{ loading ? '查询中...' : '获取数据预览 →' }}
        </Button>
      </div>
    </div>

    <!-- ── Step 2: 数据预览 ── -->
    <div v-if="step === 'preview'" class="space-y-5">

      <!-- 上课记录预览 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3 border-b border-border">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-white bg-accent px-2 py-0.5 rounded-full">上课记录</span>
            <span class="text-sm font-medium text-text-heading">共 {{ previewData?.class_preview?.total_rows?.toLocaleString() }} 条</span>
          </div>
          <span class="text-xs text-text-light">显示前 10 条</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="bg-chip">
              <tr>
                <th v-for="col in previewData?.class_preview?.columns" :key="col"
                  class="px-3 py-2 text-left text-text-light font-medium whitespace-nowrap">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in previewData?.class_preview?.rows" :key="i"
                class="border-t border-border hover:bg-pageBg">
                <td v-for="(cell, j) in row" :key="j"
                  class="px-3 py-2 text-text-heading whitespace-nowrap max-w-[200px] truncate" :title="cell">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 财务明细预览 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3 border-b border-border">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-white bg-[#2563EB] px-2 py-0.5 rounded-full">财务明细</span>
            <span class="text-sm font-medium text-text-heading">共 {{ previewData?.finance_preview?.total_rows?.toLocaleString() }} 条</span>
          </div>
          <span class="text-xs text-text-light">显示前 10 条</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="bg-chip">
              <tr>
                <th v-for="col in previewData?.finance_preview?.columns" :key="col"
                  class="px-3 py-2 text-left text-text-light font-medium whitespace-nowrap">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in previewData?.finance_preview?.rows" :key="i"
                class="border-t border-border hover:bg-pageBg">
                <td v-for="(cell, j) in row" :key="j"
                  class="px-3 py-2 text-text-heading whitespace-nowrap max-w-[200px] truncate" :title="cell">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 识别到的教练 -->
      <div v-if="previewData?.coaches?.length" class="bg-white rounded-2xl border border-border p-5">
        <p class="text-sm font-semibold text-text-heading mb-3">识别到的教练（{{ previewData.coaches.length }} 人）</p>
        <div class="flex flex-wrap gap-2">
          <span v-for="coach in previewData.coaches" :key="coach"
            class="bg-chip text-text-heading text-xs px-3 py-1 rounded-full">{{ coach }}</span>
        </div>
      </div>

      <!-- 全量数据查看 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <button
          class="w-full flex items-center justify-between px-5 py-3.5 hover:bg-pageBg transition-colors"
          @click="toggleFullData"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-text-heading">全量数据查看</span>
            <span class="text-xs text-text-light">可搜索、分页浏览原始数据，用于核对</span>
          </div>
          <span class="text-xs text-text-light">{{ fullDataVisible ? '▲ 收起' : '▼ 展开' }}</span>
        </button>

        <div v-if="fullDataVisible" class="border-t border-border">
          <!-- Tab + 搜索 -->
          <div class="flex items-center gap-3 px-5 py-3 border-b border-border bg-pageBg flex-wrap">
            <div class="flex gap-1">
              <button
                @click="fullDataTable = 'class'"
                class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                :class="fullDataTable === 'class' ? 'bg-accent text-white' : 'bg-white border border-border text-text-light hover:text-accent'"
              >上课记录</button>
              <button
                @click="fullDataTable = 'finance'"
                class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                :class="fullDataTable === 'finance' ? 'bg-accent text-white' : 'bg-white border border-border text-text-light hover:text-accent'"
              >财务明细</button>
            </div>
            <input
              v-model="fullDataSearch"
              placeholder="搜索（课程名称、教练…）"
              class="flex-1 min-w-40 rounded-lg border border-border bg-white px-3 py-1.5 text-sm text-text-heading placeholder-text-light focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <span v-if="fullDataResult" class="text-xs text-text-light flex-shrink-0">
              共 {{ fullDataResult.total.toLocaleString() }} 条
            </span>
          </div>

          <!-- 表格 -->
          <div class="overflow-x-auto" style="max-height: 480px; overflow-y: auto;">
            <div v-if="fullDataLoading" class="flex items-center justify-center py-12 text-sm text-text-light">
              加载中…
            </div>
            <table v-else-if="fullDataResult?.rows?.length" class="w-full text-xs">
              <thead class="bg-chip sticky top-0 z-10">
                <tr>
                  <th v-for="col in fullDataResult.columns" :key="col"
                    class="px-3 py-2 text-left text-text-light font-medium whitespace-nowrap border-b border-border">
                    {{ col }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in fullDataResult.rows" :key="ri"
                  class="border-t border-border hover:bg-pageBg">
                  <td v-for="(cell, ci) in row" :key="ci"
                    class="px-3 py-2 text-text-heading whitespace-nowrap max-w-[220px] truncate"
                    :title="cell">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else-if="fullDataResult && !fullDataResult.rows?.length"
              class="py-12 text-center text-sm text-text-light">无匹配数据</div>
          </div>

          <!-- 分页 -->
          <div v-if="fullDataResult && fullDataResult.total_pages > 1"
            class="flex items-center justify-between px-5 py-3 border-t border-border bg-pageBg">
            <span class="text-xs text-text-light">
              第 {{ fullDataPage }} / {{ fullDataResult.total_pages }} 页，每页 {{ fullDataPageSize }} 条
            </span>
            <div class="flex items-center gap-1">
              <button @click="goFullDataPage(1)" :disabled="fullDataPage === 1"
                class="px-2 py-1 text-xs rounded border border-border disabled:opacity-40 hover:border-accent hover:text-accent transition-colors">«</button>
              <button @click="goFullDataPage(fullDataPage - 1)" :disabled="fullDataPage === 1"
                class="px-2 py-1 text-xs rounded border border-border disabled:opacity-40 hover:border-accent hover:text-accent transition-colors">‹</button>
              <span class="px-3 py-1 text-xs">{{ fullDataPage }}</span>
              <button @click="goFullDataPage(fullDataPage + 1)" :disabled="fullDataPage >= fullDataResult.total_pages"
                class="px-2 py-1 text-xs rounded border border-border disabled:opacity-40 hover:border-accent hover:text-accent transition-colors">›</button>
              <button @click="goFullDataPage(fullDataResult.total_pages)" :disabled="fullDataPage >= fullDataResult.total_pages"
                class="px-2 py-1 text-xs rounded border border-border disabled:opacity-40 hover:border-accent hover:text-accent transition-colors">»</button>
            </div>
          </div>
        </div>
      </div>

      <div class="flex justify-between">
        <Button variant="secondary" @click="step = 'setup'">← 修改 SQL</Button>
        <Button @click="step = 'new_classes'">配置排除规则 →</Button>
      </div>
    </div>

    <!-- ── Step 3: 新开班配置 ── -->
    <div v-if="step === 'new_classes'" class="space-y-5">

      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">新开班配置</h2>
          <p class="text-xs text-text-light mt-0.5">
            新开班期间课次不计入到课率，但正常计费。开课日期起 <strong>57 天</strong>后自动结束。
          </p>
        </div>

        <!-- 添加表单 -->
        <div class="px-5 py-4 border-b border-border bg-pageBg">
          <div class="flex items-end gap-3 flex-wrap">
            <div class="flex-1 min-w-48">
              <label class="block text-xs text-text-light mb-1">课程名称</label>
              <input
                v-model="newClassInput.course_name"
                list="course-name-list"
                placeholder="输入或选择课程名称"
                @keydown.enter="addNewClass"
                class="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent placeholder-text-light"
              />
              <datalist id="course-name-list">
                <option v-for="cn in previewData?.all_course_names" :key="cn" :value="cn" />
              </datalist>
            </div>
            <div>
              <label class="block text-xs text-text-light mb-1">开课日期</label>
              <input
                v-model="newClassInput.start_date"
                type="date"
                @keydown.enter="addNewClass"
                class="rounded-lg border border-border bg-white px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
            <div v-if="newClassInput.start_date" class="pb-0.5">
              <p class="text-xs text-text-light mb-1">结束日期（自动）</p>
              <p class="text-sm text-accent font-medium py-2">{{ computeEndDate(newClassInput.start_date) }}</p>
            </div>
            <button
              @click="addNewClass"
              class="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
            >+ 添加</button>
          </div>
        </div>

        <!-- 已配置列表 -->
        <div v-if="newClasses.length === 0" class="px-5 py-8 text-center text-sm text-text-light">
          暂无新开班配置，所有课次均计入到课率
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-chip">
              <tr>
                <th class="px-5 py-2.5 text-left text-text-light font-medium">课程名称</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-36">开课日期</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-36">结束日期（+57天）</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-20">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="nc in newClasses" :key="nc.id" class="border-t border-border hover:bg-pageBg">
                <td class="px-5 py-3 text-text-heading font-medium">{{ nc.course_name }}</td>
                <td class="px-5 py-3 text-center text-text-heading">{{ nc.start_date }}</td>
                <td class="px-5 py-3 text-center text-text-light">{{ nc.end_date }}</td>
                <td class="px-5 py-3 text-center">
                  <button @click="removeNewClass(nc.id)"
                    class="text-xs px-2 py-1 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 到课率排除关键词 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">到课率排除关键词</h2>
          <p class="text-xs text-text-light mt-0.5">
            课程名称中含以下关键词的课次，<strong>不计入到课率统计</strong>，但仍正常计费（与新开班相同）。
          </p>
        </div>
        <div class="px-5 py-4 space-y-3">
          <!-- 现有关键词 chip 列表 -->
          <div class="flex flex-wrap gap-2 min-h-[36px]">
            <div v-if="exclusionKeywords.length === 0" class="text-xs text-text-light self-center">暂无关键词</div>
            <span
              v-for="kw in exclusionKeywords" :key="kw"
              class="inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 text-xs px-3 py-1 rounded-full"
            >
              {{ kw }}
              <button
                @click="removeExclusionKeyword(kw)"
                class="text-amber-400 hover:text-amber-700 transition-colors leading-none"
                title="删除"
              >×</button>
            </span>
          </div>
          <!-- 添加新关键词 -->
          <div class="flex items-center gap-2">
            <input
              v-model="newKeywordInput"
              placeholder="输入关键词，如：假期、寒假"
              @keydown.enter="addExclusionKeyword"
              class="flex-1 max-w-xs rounded-lg border border-border bg-pageBg px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent placeholder-text-light"
            />
            <button
              @click="addExclusionKeyword"
              class="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
            >+ 添加</button>
          </div>
          <p class="text-xs text-text-light">
            默认包含「假期」，课程名中带有该词的课次将被排除出到课率计算。
          </p>
        </div>
      </div>

      <!-- 指定放假日期 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">指定放假日期</h2>
          <p class="text-xs text-text-light mt-0.5">
            该日期内所有课次<strong>不计入到课率统计</strong>，但仍正常计费。适用于临时放假、节假日调课等场景。
          </p>
        </div>
        <div class="px-5 py-4 space-y-3">
          <!-- 已添加日期列表 -->
          <div class="flex flex-wrap gap-2 min-h-[36px]">
            <div v-if="exclusionDates.length === 0" class="text-xs text-text-light self-center">暂无指定日期</div>
            <span
              v-for="d in exclusionDates" :key="d"
              class="inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-700 text-xs px-3 py-1 rounded-full font-mono"
            >
              {{ d }}
              <button
                @click="removeExclusionDate(d)"
                class="text-blue-400 hover:text-blue-700 transition-colors leading-none"
                title="删除"
              >×</button>
            </span>
          </div>
          <!-- 添加日期 -->
          <div class="flex items-center gap-2">
            <input
              v-model="newDateInput"
              type="date"
              @keydown.enter="addExclusionDate"
              class="rounded-lg border border-border bg-pageBg px-3 py-2 text-sm text-text-heading focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <button
              @click="addExclusionDate"
              class="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
            >+ 添加</button>
          </div>
        </div>
      </div>

      <div class="flex justify-between">
        <Button variant="secondary" @click="step = 'preview'">← 返回预览</Button>
        <div class="flex items-center gap-2">
          <span v-if="saveSuccessMsg" class="text-xs text-accent">{{ saveSuccessMsg }}</span>
          <Button variant="secondary" :disabled="loading" @click="exportNewClassRules">导出配置</Button>
          <Button variant="secondary" :disabled="loading" @click="saveNewClassRules">保存配置</Button>
          <Button @click="step = 'capacity'">配置应到人数 →</Button>
        </div>
      </div>
    </div>

    <!-- ── Step 4: 应到人数配置 ── -->
    <div v-if="step === 'capacity'" class="space-y-5">

      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <div>
            <h2 class="text-sm font-semibold text-text-heading">班级应到人数配置</h2>
            <p class="text-xs text-text-light mt-0.5">
              到课率 = 当月实际已到人数 ÷（应到人数 × 上课次数）。已被关键词排除的课程不在此显示。
            </p>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 ml-4">
            <button
              @click="showCapacityImport = !showCapacityImport"
              class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
              :class="showCapacityImport
                ? 'border-accent text-accent bg-accent/5'
                : 'border-border text-text-heading hover:border-accent hover:text-accent'"
            >{{ showCapacityImport ? '收起' : '⬆ 导入' }}</button>
            <span v-if="unconfiguredCapacityCount === 0 && sortedCapacityCourses.length > 0"
              class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">✓ 全部已配置</span>
            <span v-else-if="unconfiguredCapacityCount > 0"
              class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              ⚠️ {{ unconfiguredCapacityCount }} 个未填写
            </span>
          </div>
        </div>

        <!-- 导入面板 -->
        <div v-if="showCapacityImport" class="px-5 py-4 border-b border-border bg-pageBg space-y-3">
          <p class="text-xs text-text-light">
            <strong>方式一：粘贴表格数据</strong>——从 Excel / 表格中复制「课程名称」和「应到人数」两列，直接粘贴到下方文本框（Tab 分隔）。
          </p>
          <textarea
            v-model="capacityImportText"
            rows="8"
            placeholder="滨江足球周六培优3班 26年春	15&#10;西溪足球周日培优4班 26年春	14&#10;…"
            class="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm font-mono text-text-heading placeholder-text-light focus:outline-none focus:ring-1 focus:ring-accent resize-y"
          />
          <div class="flex items-center gap-3 flex-wrap">
            <button
              @click="applyCapacityImportText"
              class="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
            >导入粘贴数据</button>
            <span class="text-xs text-text-light">或</span>
            <label class="cursor-pointer px-4 py-2 rounded-lg border border-border text-sm text-text-heading hover:border-accent hover:text-accent transition-colors">
              导入 JSON 文件
              <input type="file" accept=".json" class="hidden" @change="handleCapacityFileImport" />
            </label>
          </div>
          <p v-if="capacityImportError" class="text-xs text-red-600">⚠️ {{ capacityImportError }}</p>
        </div>

        <div v-if="sortedCapacityCourses.length === 0" class="px-5 py-8 text-center text-sm text-text-light">
          <span v-if="Object.keys(classCapacity).length === 0">请先完成「获取数据预览」，课程列表将自动加载</span>
          <span v-else>所有课程均已被排除关键词过滤，无需配置应到人数</span>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-chip">
              <tr>
                <th class="px-5 py-2.5 text-left text-text-light font-medium">课程名称</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-40">应到人数（人/次）</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-24">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="cn in sortedCapacityCourses" :key="cn"
                class="border-t border-border transition-colors"
                :class="(classCapacity[cn] ?? 0) > 0 ? 'hover:bg-pageBg' : 'bg-amber-50'"
              >
                <td class="px-5 py-2.5 text-text-heading">{{ cn }}</td>
                <td class="px-5 py-2.5 text-center">
                  <input
                    v-model.number="classCapacity[cn]"
                    type="number" min="0" max="999"
                    @change="saveNewClassesToStorage"
                    class="w-24 rounded-lg border px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    :class="(classCapacity[cn] ?? 0) > 0 ? 'border-border bg-pageBg' : 'border-amber-300 bg-amber-50'"
                  />
                </td>
                <td class="px-5 py-2.5 text-center">
                  <span v-if="(classCapacity[cn] ?? 0) > 0" class="text-xs text-green-600 font-medium">✓ 已配置</span>
                  <span v-else class="text-xs text-amber-600 font-medium">⚠️ 未填写</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex justify-between">
        <Button variant="secondary" @click="step = 'new_classes'">← 返回排除配置</Button>
        <div class="flex items-center gap-2">
          <span v-if="saveSuccessMsg" class="text-xs text-accent">{{ saveSuccessMsg }}</span>
          <Button variant="secondary" :disabled="loading" @click="exportNewClassRules">导出配置</Button>
          <Button variant="secondary" :disabled="loading" @click="saveNewClassRules">保存配置</Button>
          <Button @click="step = 'rules'">配置费率规则 →</Button>
        </div>
      </div>
    </div>

    <!-- ── Step 4: 费率规则 ── -->
    <div v-if="step === 'rules'" class="space-y-5">

      <!-- 超时判断规则 -->
      <div class="bg-white rounded-2xl border border-border p-5">
        <h2 class="text-sm font-semibold text-text-heading mb-3">超时判断规则</h2>
        <div class="flex items-center gap-3 text-sm text-text-heading">
          <span>创建时间 − 上课日期 ≥</span>
          <input v-if="rules" v-model.number="rules.overtime_threshold_days" type="number" min="1" max="30"
            class="w-16 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
          <span>天 → 标记为「超时」</span>
        </div>
        <p class="text-xs text-text-light mt-2">仅对「已到」状态的记录检测超时；超时课次课时费为 0，但在结果中单独列出明细</p>
      </div>

      <!-- 到课率阶梯费率（正常课包） -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">到课率阶梯费率（正常课包）</h2>
          <p class="text-xs text-text-light mt-0.5">
            按教练当月「实际满班到课率」区间适用对应单价（元 / 人次）。新开班课次按同教练相同阶梯计费。
          </p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-chip">
              <tr>
                <th class="px-5 py-2.5 text-left text-text-light font-medium">到课率区间</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium">⚽ 足球（元/人次）</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium">🏀 篮球（元/人次）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(tier, i) in editingTiers" :key="i" class="border-t border-border hover:bg-pageBg">
                <td class="px-5 py-3 text-text-light text-xs font-medium">{{ tierLabel(i) }}</td>
                <td class="px-5 py-3 text-center">
                  <input v-model.number="tier.football" type="number" min="0"
                    class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
                </td>
                <td class="px-5 py-3 text-center">
                  <input v-model.number="tier.basketball" type="number" min="0"
                    class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 特殊课包费率 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">特殊课包费率</h2>
        </div>
        <div class="divide-y divide-border">
          <!-- 跃动课包 -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-sm font-medium text-text-heading">跃动课包</span>
              <span class="text-xs text-text-light ml-2">固定单价，不受到课率影响</span>
            </div>
            <div class="flex items-center gap-2">
              <input v-model.number="editingSpecialFees.yuedong_per_session" type="number" min="0"
                class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
              <span class="text-xs text-text-light">元 / 人次</span>
            </div>
          </div>
          <!-- 一对一私教 -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-sm font-medium text-text-heading">一对一私教</span>
              <span class="text-xs text-text-light ml-2">按学员确认收入（service_amount）的比例计算</span>
            </div>
            <div class="flex items-center gap-2">
              <input v-model.number="editingSpecialFees.one_on_one_rate" type="number" min="0" max="1" step="0.01"
                class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
              <span class="text-xs text-text-light">× 确认收入</span>
            </div>
          </div>
          <!-- 168拼团 -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-sm font-medium text-text-heading">168拼团课包 / 168课包</span>
              <span class="text-xs text-text-light ml-2">课时费为 0，但会列入明细</span>
            </div>
            <span class="text-sm text-text-light italic pr-2">0 元（固定）</span>
          </div>
        </div>
      </div>

      <!-- 教练个人费率（Tab） -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">教练个人费率</h2>
          <span class="text-xs text-text-light">为特定教练配置自定义特殊课包费率（正常课包仍按阶梯计算）</span>
        </div>
        <!-- Tab 栏 -->
        <div class="flex gap-1.5 px-5 py-2.5 border-b border-border bg-pageBg overflow-x-auto">
          <button @click="activeCoachTab = 'default'"
            class="px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap flex-shrink-0 transition-colors"
            :class="activeCoachTab === 'default' ? 'bg-accent text-white' : 'bg-white border border-border text-text-light hover:text-accent hover:border-accent'">
            全局默认
          </button>
          <button v-for="coach in previewData?.coaches" :key="coach" @click="activeCoachTab = coach"
            class="px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap flex-shrink-0 transition-colors"
            :class="activeCoachTab === coach ? 'bg-accent text-white' : 'bg-white border border-border text-text-light hover:text-accent hover:border-accent'">
            {{ coach }}
          </button>
        </div>
        <!-- 教练 Tab 操作 -->
        <div v-if="activeCoachTab !== 'default'" class="flex items-center justify-between px-5 pt-4">
          <span class="text-xs text-text-light">修改后点击下方「保存并计算」即可生效</span>
          <div class="flex gap-2">
            <button @click="copyDefaultToCoach(activeCoachTab)"
              class="text-xs px-3 py-1.5 rounded-lg border border-border text-text-heading hover:border-accent hover:text-accent transition-colors">
              复制全局默认费率
            </button>
            <button @click="clearCoachFee(activeCoachTab)"
              class="text-xs px-3 py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors">
              清除个人配置
            </button>
          </div>
        </div>
        <!-- 费率表 -->
        <div class="px-5 pb-5 pt-4 space-y-5">
          <!-- ⚽ 足球 -->
          <div>
            <div class="flex items-center gap-2 mb-2.5">
              <span>⚽</span>
              <span class="text-xs font-semibold text-text-heading">足球费率</span>
              <span class="text-xs text-text-light">（元 / 课次）— 正常课包由到课率阶梯决定，此处设置无效</span>
            </div>
            <table class="w-full text-sm">
              <thead class="bg-chip">
                <tr>
                  <th class="px-5 py-2.5 text-left text-text-light font-medium w-48">课包类型</th>
                  <th class="px-5 py-2.5 text-center text-text-light font-medium">准时</th>
                  <th class="px-5 py-2.5 text-center text-text-light font-medium">超时</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pkg in footballPackages" :key="pkg"
                  class="border-t border-border hover:bg-pageBg"
                  :class="pkg === '正常课包' ? 'opacity-40' : ''">
                  <td class="px-5 py-3 text-text-heading font-medium">
                    {{ pkg }}
                    <span v-if="pkg === '正常课包'" class="text-xs text-text-light ml-1">（阶梯决定）</span>
                  </td>
                  <td class="px-5 py-3 text-center">
                    <input v-model.number="currentEditingFees.football[pkg]['准时']" type="number" min="0"
                      :disabled="pkg === '正常课包'"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-40" />
                  </td>
                  <td class="px-5 py-3 text-center">
                    <input v-model.number="currentEditingFees.football[pkg]['超时']" type="number" min="0"
                      :disabled="true"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm opacity-40" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- 🏀 篮球 -->
          <div>
            <div class="flex items-center gap-2 mb-2.5">
              <span>🏀</span>
              <span class="text-xs font-semibold text-text-heading">篮球费率</span>
              <span class="text-xs text-text-light">（元 / 课次）— 正常课包由到课率阶梯决定，此处设置无效</span>
            </div>
            <table class="w-full text-sm">
              <thead class="bg-chip">
                <tr>
                  <th class="px-5 py-2.5 text-left text-text-light font-medium w-48">课包类型</th>
                  <th class="px-5 py-2.5 text-center text-text-light font-medium">准时</th>
                  <th class="px-5 py-2.5 text-center text-text-light font-medium">超时</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pkg in basketballPackages" :key="pkg"
                  class="border-t border-border hover:bg-pageBg"
                  :class="pkg === '正常课包' ? 'opacity-40' : ''">
                  <td class="px-5 py-3 text-text-heading font-medium">
                    {{ pkg }}
                    <span v-if="pkg === '正常课包'" class="text-xs text-text-light ml-1">（阶梯决定）</span>
                  </td>
                  <td class="px-5 py-3 text-center">
                    <input v-model.number="currentEditingFees.basketball[pkg]['准时']" type="number" min="0"
                      :disabled="pkg === '正常课包' || pkg === '一对一私教'"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-40" />
                  </td>
                  <td class="px-5 py-3 text-center">
                    <input v-model.number="currentEditingFees.basketball[pkg]['超时']" type="number" min="0"
                      :disabled="true"
                      class="w-24 rounded-lg border border-border bg-pageBg px-2 py-1 text-center text-sm opacity-40" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 课包分类配置（直接映射） -->
      <div v-if="Object.keys(editingCoursePackMapping).length" class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div class="flex items-center gap-2">
            <h2 class="text-sm font-semibold text-text-heading">课包分类配置</h2>
            <span v-if="unknownSportCount > 0"
              class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              {{ unknownSportCount }} 个未指定球类
            </span>
            <span v-else class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">✓ 全部已分类</span>
          </div>
          <span class="text-xs text-text-light">共 {{ Object.keys(editingCoursePackMapping).length }} 个课包</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-chip">
              <tr>
                <th class="px-5 py-2.5 text-left text-text-light font-medium">课包名称</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-36">球类</th>
                <th class="px-5 py-2.5 text-center text-text-light font-medium w-40">课包类型</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(mapping, pack) in editingCoursePackMapping" :key="pack"
                class="border-t border-border transition-colors"
                :class="mapping.sport === 'unknown' ? 'bg-amber-50' : 'hover:bg-pageBg'">
                <td class="px-5 py-2.5 text-text-heading">{{ pack }}</td>
                <td class="px-5 py-2.5 text-center">
                  <select v-model="mapping.sport" @change="onCourseSportChange(pack as string)"
                    class="text-xs rounded-lg border px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-accent"
                    :class="mapping.sport === 'unknown'    ? 'border-amber-300 bg-amber-50 text-amber-700'
                           : mapping.sport === 'football'  ? 'border-green-300 bg-green-50 text-green-700'
                           :                                 'border-orange-300 bg-orange-50 text-orange-700'">
                    <option value="unknown">? 未知</option>
                    <option value="football">⚽ 足球</option>
                    <option value="basketball">🏀 篮球</option>
                  </select>
                </td>
                <td class="px-5 py-2.5 text-center">
                  <select v-if="mapping.sport !== 'unknown'" v-model="mapping.pkg_type"
                    class="text-xs rounded-lg border border-border bg-pageBg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-accent">
                    <option v-for="pkg in pkgOptionsForSport(mapping.sport)" :key="pkg" :value="pkg">{{ pkg }}</option>
                  </select>
                  <span v-else class="text-xs text-text-light">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex justify-between">
        <Button variant="secondary" @click="step = 'capacity'">← 返回应到人数</Button>
        <div class="flex items-center gap-2">
          <span v-if="saveSuccessMsg" class="text-xs text-accent">{{ saveSuccessMsg }}</span>
          <Button variant="secondary" :disabled="loading" @click="exportRules">导出规则</Button>
          <Button variant="secondary" :disabled="loading" @click="saveRulesOnly">暂存规则</Button>
          <Button :disabled="loading" @click="saveRulesAndCalculate">
            {{ loading ? '计算中...' : '保存并计算课时费 →' }}
          </Button>
        </div>
      </div>
    </div>

    <!-- ── Step 5: 计算结果 ── -->
    <div v-if="step === 'result'" class="space-y-5">

      <!-- 统计卡片 -->
      <div class="grid grid-cols-4 gap-4">
        <div class="bg-white rounded-2xl border border-border p-4 text-center">
          <p class="text-2xl font-bold text-text-heading">{{ stats.coach_count }}</p>
          <p class="text-xs text-text-light mt-1">参与教练</p>
        </div>
        <div class="bg-white rounded-2xl border border-border p-4 text-center">
          <p class="text-2xl font-bold text-text-heading">{{ stats.session_count }}</p>
          <p class="text-xs text-text-light mt-1">总人次</p>
        </div>
        <div class="bg-white rounded-2xl border border-border p-4 text-center">
          <p class="text-2xl font-bold text-amber-600">{{ stats.overtime_count }}</p>
          <p class="text-xs text-text-light mt-1">超时人次</p>
        </div>
        <div class="bg-white rounded-2xl border border-border p-4 text-center">
          <p class="text-2xl font-bold text-accent">¥{{ grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</p>
          <p class="text-xs text-text-light mt-1">课时费合计</p>
        </div>
      </div>

      <!-- 未配置应到人数警告 -->
      <div v-if="stats.missing_capacity_courses?.length"
        class="bg-amber-50 border border-amber-200 rounded-2xl px-5 py-4">
        <p class="text-sm font-medium text-amber-800 mb-2">⚠️ 以下课程未配置应到人数，已从到课率计算中排除</p>
        <div class="flex flex-wrap gap-2">
          <span v-for="c in stats.missing_capacity_courses" :key="c"
            class="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded-full">{{ c }}</span>
        </div>
        <p class="text-xs text-amber-600 mt-2">请返回「排除配置」→「班级应到人数配置」补充填写，再重新计算。</p>
      </div>

      <!-- 未识别球类警告 -->
      <div v-if="stats.unmatched_sport_courses?.length"
        class="bg-amber-50 border border-amber-200 rounded-2xl px-5 py-4">
        <p class="text-sm font-medium text-amber-800 mb-2">⚠️ 以下课程未能识别球类（不计入费用）</p>
        <div class="flex flex-wrap gap-2">
          <span v-for="c in stats.unmatched_sport_courses" :key="c"
            class="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded-full">{{ c }}</span>
        </div>
        <p class="text-xs text-amber-600 mt-2">请在「费率规则」→「课包分类配置」中手动指定球类。</p>
      </div>

      <!-- 超时明细（调试用） -->
      <div v-if="stats.overtime_details?.length" class="bg-white rounded-2xl border border-border overflow-hidden">
        <button
          class="w-full flex items-center justify-between px-5 py-3.5 hover:bg-pageBg transition-colors"
          @click="overtimeDetailVisible = !overtimeDetailVisible"
        >
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-semibold text-text-heading">超时明细</span>
            <span class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
              {{ stats.overtime_details.length }} 课次 · {{ stats.overtime_student_count }} 学员 · 阈值 ≥ {{ stats.overtime_threshold_days }} 天
            </span>
            <!-- 超时匹配模式标签 -->
            <span v-if="stats.overtime_match_mode === 'per_student'"
              class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
              ✓ 按学员精确匹配
            </span>
            <span v-else
              class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium"
              :title="`上课记录会员列: ${stats.overtime_match_debug?.class_member_col ?? '未找到'} · 财务明细会员列: ${stats.overtime_match_debug?.finance_member_col ?? '未找到'}`"
            >
              ⚠ 整课匹配（SQL 中需加会员姓名字段）
            </span>
            <span class="text-xs text-text-light">展开可核对每条超时记录</span>
          </div>
          <span class="text-xs text-text-light">{{ overtimeDetailVisible ? '▲ 收起' : '▼ 展开' }}</span>
        </button>
        <div v-if="overtimeDetailVisible" class="overflow-x-auto border-t border-border">
          <table class="w-full text-xs">
            <thead class="bg-chip">
              <tr>
                <th class="px-4 py-2.5 text-left text-text-light font-medium w-24">教练</th>
                <th class="px-4 py-2.5 text-left text-text-light font-medium">课程名称</th>
                <th class="px-4 py-2.5 text-center text-text-light font-medium w-28">上课日期</th>
                <th class="px-4 py-2.5 text-center text-text-light font-medium w-28">最晚创建日期</th>
                <th class="px-4 py-2.5 text-center text-text-light font-medium w-24">晚了（天）</th>
                <th class="px-4 py-2.5 text-center text-text-light font-medium w-24">超时学员数</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(d, i) in stats.overtime_details" :key="i">
                <!-- 教练分组标题行：同一教练的第一条记录 -->
                <tr v-if="i === 0 || d.coach !== stats.overtime_details[i - 1].coach"
                  class="bg-amber-50/60 border-t border-amber-200">
                  <td colspan="6" class="px-4 py-2 font-semibold text-amber-800 text-xs">
                    {{ d.coach }}
                    <span class="ml-2 font-normal text-amber-600">
                      共 {{ stats.overtime_details.filter((x: any) => x.coach === d.coach).length }} 条课次 ·
                      {{ stats.overtime_details.filter((x: any) => x.coach === d.coach).reduce((s: number, x: any) => s + x.late_count, 0) }} 名学员
                    </span>
                  </td>
                </tr>
                <tr class="border-t border-border hover:bg-amber-50">
                  <td class="px-4 py-2.5 text-text-light">{{ d.coach }}</td>
                  <td class="px-4 py-2.5 text-text-heading">{{ d.course }}</td>
                  <td class="px-4 py-2.5 text-center text-text-heading">{{ d.date }}</td>
                  <td class="px-4 py-2.5 text-center text-text-light">{{ d.latest_created }}</td>
                  <td class="px-4 py-2.5 text-center font-medium text-amber-600">{{ d.max_days_late }}</td>
                  <td class="px-4 py-2.5 text-center text-text-heading">{{ d.late_count }}</td>
                </tr>
              </template>
            </tbody>
            <tfoot>
              <tr class="bg-chip border-t-2 border-border">
                <td class="px-4 py-2.5 font-semibold text-text-heading" colspan="3">合计</td>
                <td class="px-4 py-2.5 text-center text-text-light">—</td>
                <td class="px-4 py-2.5 text-center text-text-light">—</td>
                <td class="px-4 py-2.5 text-center font-semibold text-amber-600">{{ stats.overtime_student_count }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- 课时费明细表 -->
      <div class="bg-white rounded-2xl border border-border overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3 border-b border-border">
          <h2 class="text-sm font-semibold text-text-heading">教练课时费明细</h2>
          <Button size="small" @click="downloadExcel" :disabled="!downloadFilename">⬇ 下载 Excel</Button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs border-collapse">
            <thead class="bg-chip sticky top-0">
              <tr>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-10">序号</th>
                <th class="px-3 py-2.5 text-left text-text-light font-medium border border-border">校区</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-20">姓名</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-14">师资</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-20">到课率</th>
                <th class="px-3 py-2.5 text-left text-text-light font-medium border border-border">计费课包</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-18">应付课时</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-20">金额</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-24">个人课时合计</th>
                <th class="px-3 py-2.5 text-center text-text-light font-medium border border-border w-24">应发课时费</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(coach, ci) in coachResults" :key="coach.coach">
                <tr v-for="(line, li) in coach.lines" :key="line.label"
                  :class="line.is_overtime ? 'bg-amber-50' : (li % 2 === 0 ? '' : 'bg-pageBg/50')">
                  <!-- 合并单元格：序号 -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-2 py-2 text-center text-text-light border border-border font-medium align-middle">
                    {{ ci + 1 }}
                  </td>
                  <!-- 校区 -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-text-heading border border-border align-middle text-xs">
                    {{ coach.campus || '—' }}
                  </td>
                  <!-- 姓名 -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-center font-semibold text-text-heading border border-border align-middle">
                    {{ coach.coach }}
                  </td>
                  <!-- 师资 -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-center text-text-heading border border-border align-middle">
                    {{ coach.quality || '—' }}
                  </td>
                  <!-- 到课率 -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-center border border-border align-middle">
                    <span v-if="coach.attendance_rate != null"
                      class="font-medium"
                      :class="coach.attendance_rate >= 0.9 ? 'text-green-600'
                            : coach.attendance_rate >= 0.7 ? 'text-accent'
                            :                               'text-amber-600'">
                      {{ (coach.attendance_rate * 100).toFixed(2) }}%
                    </span>
                    <span v-else class="text-text-light">—</span>
                    <div v-if="coach.attendance_stats" class="text-[10px] text-text-light mt-0.5">
                      {{ coach.attendance_stats.attended }}/{{ coach.attendance_stats.total }}
                    </div>
                  </td>
                  <!-- 计费课包 -->
                  <td class="px-3 py-2 border border-border">
                    <span :class="line.is_overtime ? 'text-amber-600' : 'text-text-heading'">
                      {{ line.label }}
                    </span>
                  </td>
                  <!-- 应付课时 -->
                  <td class="px-3 py-2 text-center text-text-heading border border-border">{{ line.count }}</td>
                  <!-- 金额（单价） -->
                  <td class="px-3 py-2 text-center border border-border"
                    :class="line.total_fee === 0 ? 'text-text-light' : 'text-text-heading'">
                    {{ line.total_fee === 0 ? '0.00' : line.unit_fee.toFixed(2) }}
                  </td>
                  <!-- 个人课时合计（合并） -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-center font-semibold text-text-heading border border-border align-middle">
                    {{ coach.total.toFixed(2) }}
                  </td>
                  <!-- 应发课时费（合并） -->
                  <td v-if="li === 0" :rowspan="coach.lines.length"
                    class="px-3 py-2 text-center font-bold text-accent border border-border align-middle">
                    {{ coach.total.toFixed(2) }}
                  </td>
                </tr>
              </template>
            </tbody>
            <!-- 合计行 -->
            <tfoot>
              <tr class="bg-chip border-t-2 border-border">
                <td class="px-3 py-3 text-center font-bold text-text-heading border border-border" colspan="5">合计</td>
                <td class="px-3 py-3 text-center text-text-light border border-border">—</td>
                <td class="px-3 py-3 text-center font-bold text-text-heading border border-border">{{ stats.session_count }}</td>
                <td class="px-3 py-3 text-center border border-border">—</td>
                <td class="px-3 py-3 text-center font-bold text-accent border border-border">
                  {{ grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
                </td>
                <td class="px-3 py-3 text-center font-bold text-accent border border-border">
                  {{ grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div class="flex justify-between">
        <Button variant="secondary" @click="step = 'rules'">← 调整规则</Button>
        <Button @click="downloadExcel" :disabled="!downloadFilename">⬇ 下载 Excel</Button>
      </div>
    </div>

  </div>
</template>
