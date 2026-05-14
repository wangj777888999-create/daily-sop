<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

const API = '/api/tools/photo-checkin/validate'
const API_URLS = '/api/tools/photo-checkin/validate-urls'
const TRAIN_API = '/api/tools/yolo-training'

// ─────────────────────────────────────────────────────────
//  参数配置
// ─────────────────────────────────────────────────────────

interface FilterConfig {
  conf_threshold: number
  min_bbox_ratio: number
  edge_margin_pct: number
  iou_threshold: number
  imgsz: number
}

const PRESETS: Record<string, { label: string; hint: string; cfg: FilterConfig }> = {
  default: {
    label: '默认',
    hint: '适合人物间距清晰、照片质量较好的情况',
    cfg: { conf_threshold: 0.45, min_bbox_ratio: 0.008, edge_margin_pct: 0.05, iou_threshold: 0.45, imgsz: 640 },
  },
  crowded: {
    label: '人群堆叠',
    hint: '人物相互遮挡或密集排列：降低 NMS IoU，允许相邻框共存',
    cfg: { conf_threshold: 0.30, min_bbox_ratio: 0.003, edge_margin_pct: 0.03, iou_threshold: 0.30, imgsz: 640 },
  },
  blurry: {
    label: '低质/模糊',
    hint: '像素不足或远景照片：降低置信度阈值 + 提高推理分辨率',
    cfg: { conf_threshold: 0.25, min_bbox_ratio: 0.004, edge_margin_pct: 0.05, iou_threshold: 0.45, imgsz: 960 },
  },
  strict: {
    label: '严格',
    hint: '只保留高置信度、较大的人体检测框，减少误检',
    cfg: { conf_threshold: 0.60, min_bbox_ratio: 0.012, edge_margin_pct: 0.08, iou_threshold: 0.60, imgsz: 640 },
  },
}

const config = reactive<FilterConfig>({ ...PRESETS.default.cfg })

function applyPreset(key: string) {
  Object.assign(config, PRESETS[key].cfg)
}

const activePresetKey = computed(() =>
  Object.entries(PRESETS).find(([, p]) => JSON.stringify(p.cfg) === JSON.stringify({ ...config }))?.[0] ?? null
)

// ─────────────────────────────────────────────────────────
//  类型定义
// ─────────────────────────────────────────────────────────

interface Box {
  conf: number
  edge_flag?: boolean
  x1: number; y1: number; x2: number; y2: number
}

interface RejectedBox extends Box {
  rejected_reason: string
}

interface PhotoResult {
  filename: string
  detected_count: number
  raw_count: number
  confidence_avg: number
  annotated_image_b64: string | null
  boxes: Box[]
  rejected_boxes?: RejectedBox[]
  filter_config: FilterConfig
  error: string | null
  source_url?: string          // URL 导入时有值
  // 用户输入
  ground_truth: number | null
  // 用户编辑过的最终框（用于保存训练样本）
  confirmed_boxes: Box[]
  img_width: number
  img_height: number
  sample_saved: boolean
}

// ─────────────────────────────────────────────────────────
//  输入模式：文件上传 vs URL 导入
// ─────────────────────────────────────────────────────────

type InputMode = 'file' | 'url'
const inputMode = ref<InputMode>('file')

function switchInputMode(m: InputMode) {
  inputMode.value = m
  results.value = []
  activeIdx.value = null
  errorMsg.value = ''
  urlErrors.value = []
}

// ─────────────────────────────────────────────────────────
//  图片上传 + 推理
// ─────────────────────────────────────────────────────────

const uploadedFiles = ref<File[]>([])
const results = ref<PhotoResult[]>([])
const running = ref(false)
const errorMsg = ref('')
const showRejected = ref(true)
const activeIdx = ref<number | null>(null)

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    uploadedFiles.value = Array.from(input.files).slice(0, 20)
    results.value = []
    activeIdx.value = null
    errorMsg.value = ''
  }
  input.value = ''
}

function removeFile(i: number) {
  uploadedFiles.value.splice(i, 1)
  if (activeIdx.value === i) activeIdx.value = null
}

async function runValidation() {
  if (!uploadedFiles.value.length) return
  running.value = true
  errorMsg.value = ''
  try {
    const form = new FormData()
    uploadedFiles.value.forEach(f => form.append('photos', f))
    form.append('filter_config_json', JSON.stringify({ ...config }))

    const res = await fetch(API, { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '识别失败')
    }
    const data = await res.json()

    // 解析图片尺寸（从 base64 标注图推断，或后端返回时扩展）
    const prev = results.value
    results.value = (data.results as any[]).map((r, i) => ({
      ...r,
      ground_truth: prev[i]?.ground_truth ?? null,
      confirmed_boxes: [...(r.boxes ?? [])],
      img_width: 0,   // 后续从 Image 对象读取
      img_height: 0,
      sample_saved: false,
    }))

    // 从 base64 解析真实图片尺寸（用于 YOLO 标注坐标归一化）
    for (const r of results.value) {
      if (r.annotated_image_b64) {
        await resolveImageSize(r)
      }
    }

    activeIdx.value = 0
  } catch (e: any) {
    errorMsg.value = e.message || '服务异常，请确认后端已启动'
  } finally {
    running.value = false
  }
}

function resolveImageSize(r: PhotoResult): Promise<void> {
  return new Promise(resolve => {
    const img = new Image()
    img.onload = () => {
      r.img_width = img.naturalWidth
      r.img_height = img.naturalHeight
      resolve()
    }
    img.onerror = () => resolve()
    img.src = `data:image/jpeg;base64,${r.annotated_image_b64}`
  })
}

// ─────────────────────────────────────────────────────────
//  URL 批量导入
// ─────────────────────────────────────────────────────────

const urlText = ref('')
const urlErrors = ref<Array<{ url: string; error: string }>>([])

// 解析文本框里的 URL 列表（一行一条，或逗号/空格分隔，自动去重去空）
const parsedUrls = computed(() => {
  return [...new Set(
    urlText.value
      .split(/[\n,\s]+/)
      .map(s => s.trim())
      .filter(s => s.startsWith('http://') || s.startsWith('https://'))
  )].slice(0, 20)
})

async function runValidationFromUrls() {
  if (!parsedUrls.value.length) return
  running.value = true
  errorMsg.value = ''
  urlErrors.value = []
  try {
    const res = await fetch(API_URLS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: parsedUrls.value, filter_config: { ...config } }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '识别失败')
    }
    const data = await res.json()
    urlErrors.value = data.url_errors ?? []

    const prev = results.value
    results.value = (data.results as any[]).map((r: any, i: number) => ({
      ...r,
      ground_truth: prev[i]?.ground_truth ?? null,
      confirmed_boxes: [...(r.boxes ?? [])],
      img_width: 0,
      img_height: 0,
      sample_saved: false,
    }))

    for (const r of results.value) {
      if (r.annotated_image_b64) await resolveImageSize(r)
    }
    if (results.value.length > 0) activeIdx.value = 0
  } catch (e: any) {
    errorMsg.value = e.message || '服务异常，请确认后端已启动'
  } finally {
    running.value = false
  }
}

// ─────────────────────────────────────────────────────────
//  精度统计
// ─────────────────────────────────────────────────────────

const accuracyStats = computed(() => {
  const labeled = results.value.filter(r => r.ground_truth != null && !r.error)
  if (!labeled.length) return null
  const errors = labeled.map(r => Math.abs(r.detected_count - (r.ground_truth as number)))
  const mae = errors.reduce((s, e) => s + e, 0) / errors.length
  return {
    count: labeled.length,
    mae: mae.toFixed(2),
    exactAcc: ((errors.filter(e => e === 0).length / labeled.length) * 100).toFixed(0),
    within1Acc: ((errors.filter(e => e <= 1).length / labeled.length) * 100).toFixed(0),
  }
})

function diffLabel(r: PhotoResult) {
  if (r.ground_truth == null) return ''
  const d = r.detected_count - (r.ground_truth as number)
  return (d > 0 ? '+' : '') + d
}

function diffClass(r: PhotoResult) {
  if (r.ground_truth == null) return ''
  return Math.abs(r.detected_count - (r.ground_truth as number)) <= 1 ? 'text-green-600' : 'text-red-600'
}

// ─────────────────────────────────────────────────────────
//  Confirmed boxes 编辑（添加/删除）
// ─────────────────────────────────────────────────────────

const activeResult = computed(() =>
  activeIdx.value !== null ? results.value[activeIdx.value] : null
)

function removeConfirmedBox(r: PhotoResult, i: number) {
  r.confirmed_boxes.splice(i, 1)
  r.sample_saved = false
}

function addRejectedBox(r: PhotoResult, b: RejectedBox) {
  const { rejected_reason: _, ...box } = b
  r.confirmed_boxes.push({ ...box, edge_flag: false })
  r.sample_saved = false
}

// ─────────────────────────────────────────────────────────
//  保存训练样本
// ─────────────────────────────────────────────────────────

const savingIdx = ref<number | null>(null)

async function saveSample(r: PhotoResult, fileIdx: number) {
  if (!r.confirmed_boxes.length && r.ground_truth !== 0) {
    if (!confirm('当前没有确认的检测框，确定保存为「0人」样本吗？')) return
  }
  savingIdx.value = fileIdx
  try {
    const boxes = r.confirmed_boxes.map(b => ({ x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2 }))
    const noteStr = r.ground_truth != null ? `ground_truth=${r.ground_truth}` : undefined

    if (r.source_url) {
      // URL 来源：调用 save-sample-from-url
      const res = await fetch(`${TRAIN_API}/save-sample-from-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: r.source_url,
          boxes,
          img_width: r.img_width || 640,
          img_height: r.img_height || 640,
          note: noteStr,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '保存失败')
      }
    } else {
      // 文件上传来源：调用 save-sample（multipart）
      const file = uploadedFiles.value[fileIdx]
      if (!file) throw new Error('原始文件不存在，请重新上传')
      const form = new FormData()
      form.append('photo', file)
      form.append('boxes_json', JSON.stringify(boxes))
      form.append('img_width', String(r.img_width || 640))
      form.append('img_height', String(r.img_height || 640))
      if (noteStr) form.append('note', noteStr)
      const res = await fetch(`${TRAIN_API}/save-sample`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '保存失败')
      }
    }

    r.sample_saved = true
    await loadSamples()
  } catch (e: any) {
    alert(e.message)
  } finally {
    savingIdx.value = null
  }
}

// ─────────────────────────────────────────────────────────
//  训练样本列表 + 导出
// ─────────────────────────────────────────────────────────

interface SampleMeta {
  filename: string
  original_name: string
  person_count: number
  note: string | null
  saved_at: string
}

const samples = ref<SampleMeta[]>([])
const samplesLoading = ref(false)
const exporting = ref(false)
const deletingFile = ref<string | null>(null)

async function loadSamples() {
  samplesLoading.value = true
  try {
    const res = await fetch(`${TRAIN_API}/samples`)
    const data = await res.json()
    samples.value = data.samples
  } catch {
    samples.value = []
  } finally {
    samplesLoading.value = false
  }
}

async function exportDataset() {
  exporting.value = true
  try {
    const res = await fetch(`${TRAIN_API}/export-dataset?val_ratio=0.2`)
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const cd = res.headers.get('content-disposition') || ''
    const match = cd.match(/filename=(.+)/)
    a.download = match ? match[1] : 'yolo_dataset.zip'
    a.href = url
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    alert(e.message)
  } finally {
    exporting.value = false
  }
}

async function deleteSample(filename: string) {
  if (!confirm(`确认删除样本 ${filename}？`)) return
  deletingFile.value = filename
  try {
    await fetch(`${TRAIN_API}/samples/${filename}`, { method: 'DELETE' })
    await loadSamples()
  } finally {
    deletingFile.value = null
  }
}

// ─────────────────────────────────────────────────────────
//  Tab
// ─────────────────────────────────────────────────────────

type Tab = 'validate' | 'samples'
const activeTab = ref<Tab>('validate')

function switchTab(t: Tab) {
  activeTab.value = t
  if (t === 'samples') loadSamples()
}

// 参数复制
const exportCopied = ref(false)
function copyConfig() {
  navigator.clipboard.writeText(JSON.stringify({ ...config }, null, 2)).catch(() => {})
  exportCopied.value = true
  setTimeout(() => { exportCopied.value = false }, 2000)
}

onMounted(() => loadSamples())
</script>

<template>
  <div class="p-6 max-w-6xl mx-auto flex flex-col gap-5">

    <!-- Tab 切换 -->
    <div class="flex border-b border-border gap-1">
      <button
        v-for="(label, key) in { validate: '验证与调参', samples: `训练样本库 (${samples.length})` }"
        :key="key"
        class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === key
          ? 'border-accent text-accent'
          : 'border-transparent text-text-light hover:text-text-heading'"
        @click="switchTab(key as Tab)"
      >
        {{ label }}
      </button>
    </div>

    <!-- ═══════════════ TAB: 验证与调参 ═══════════════ -->
    <template v-if="activeTab === 'validate'">

      <!-- 参数配置面板 -->
      <Card>
        <div class="flex flex-col gap-4">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <h3 class="text-sm font-bold text-text-heading">推理参数配置</h3>
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs text-text-light">场景预设：</span>
              <button
                v-for="(p, key) in PRESETS" :key="key"
                class="text-xs px-2.5 py-1 rounded-full border transition-colors"
                :class="activePresetKey === key
                  ? 'border-accent bg-accent/10 text-accent font-semibold'
                  : 'border-border text-text-light hover:border-accent/60'"
                :title="p.hint"
                @click="applyPreset(key)"
              >
                {{ p.label }}
              </button>
              <button
                class="text-xs px-2.5 py-1 rounded-full border transition-colors ml-1"
                :class="exportCopied ? 'border-green-400 text-green-600' : 'border-border text-text-light hover:border-accent/60'"
                @click="copyConfig"
              >
                {{ exportCopied ? '✓ 已复制' : '复制参数' }}
              </button>
            </div>
          </div>

          <!-- 预设说明 -->
          <div v-if="activePresetKey" class="text-xs text-text-light bg-page-bg rounded-lg px-3 py-2">
            {{ PRESETS[activePresetKey].hint }}
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <!-- 置信度阈值 -->
            <div class="flex flex-col gap-1.5 lg:col-span-1">
              <div class="flex justify-between">
                <label class="text-xs font-medium text-text-body">置信度阈值</label>
                <span class="text-xs font-mono font-bold text-accent">{{ config.conf_threshold.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.10" max="0.90" step="0.01" v-model.number="config.conf_threshold" class="w-full accent-accent" />
              <p class="text-[10px] text-text-light leading-relaxed">低于此值的框丢弃。↓调低 = 检测更多但误检多；↑调高 = 更精准但漏检多</p>
            </div>

            <!-- NMS IoU（核心：堆叠人群） -->
            <div class="flex flex-col gap-1.5 lg:col-span-1">
              <div class="flex justify-between">
                <label class="text-xs font-medium text-text-body">NMS IoU 阈值</label>
                <span class="text-xs font-mono font-bold text-accent">{{ config.iou_threshold.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.10" max="0.80" step="0.01" v-model.number="config.iou_threshold" class="w-full accent-accent" />
              <p class="text-[10px] text-text-light leading-relaxed">控制相邻框合并：↓调低 = 允许相邻框共存（适合人群堆叠）；↑调高 = 合并重叠框（防重复计数）</p>
            </div>

            <!-- 推理分辨率 -->
            <div class="flex flex-col gap-1.5 lg:col-span-1">
              <div class="flex justify-between">
                <label class="text-xs font-medium text-text-body">推理分辨率</label>
                <span class="text-xs font-mono font-bold text-accent">{{ config.imgsz }}px</span>
              </div>
              <input type="range" min="320" max="1280" step="32" v-model.number="config.imgsz" class="w-full accent-accent" />
              <p class="text-[10px] text-text-light leading-relaxed">模糊/低像素照片可提高至 960/1280，代价是推理速度变慢约 2-4×</p>
            </div>

            <!-- 最小框面积比 -->
            <div class="flex flex-col gap-1.5 lg:col-span-1">
              <div class="flex justify-between">
                <label class="text-xs font-medium text-text-body">最小框面积比</label>
                <span class="text-xs font-mono font-bold text-accent">{{ config.min_bbox_ratio.toFixed(4) }}</span>
              </div>
              <input type="range" min="0.001" max="0.050" step="0.001" v-model.number="config.min_bbox_ratio" class="w-full accent-accent" />
              <p class="text-[10px] text-text-light leading-relaxed">过滤极小框（背景噪声）。人群密集或有远景时调低</p>
            </div>

            <!-- 边缘边距 -->
            <div class="flex flex-col gap-1.5 lg:col-span-1">
              <div class="flex justify-between">
                <label class="text-xs font-medium text-text-body">边缘边距比例</label>
                <span class="text-xs font-mono font-bold text-accent">{{ config.edge_margin_pct.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.00" max="0.20" step="0.01" v-model.number="config.edge_margin_pct" class="w-full accent-accent" />
              <p class="text-[10px] text-text-light leading-relaxed">顶/底边缘区域标黄（edge_flag），不影响计数，仅供分析</p>
            </div>
          </div>
        </div>
      </Card>

      <!-- 上传 + 运行 -->
      <Card>
        <div class="flex flex-col gap-4">
          <!-- 模式切换 -->
          <div class="flex items-center gap-1 bg-page-bg rounded-lg p-1 w-fit">
            <button
              v-for="(label, mode) in { file: '📁 本地文件', url: '🔗 URL 批量导入' }"
              :key="mode"
              class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
              :class="inputMode === mode
                ? 'bg-card text-text-heading shadow-sm'
                : 'text-text-light hover:text-text-heading'"
              @click="switchInputMode(mode as InputMode)"
            >
              {{ label }}
            </button>
          </div>

          <!-- ── 文件上传模式 ── -->
          <template v-if="inputMode === 'file'">
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-bold text-text-heading">上传验证照片</h3>
              <label class="cursor-pointer">
                <input type="file" accept="image/jpeg,image/png,image/webp,image/heic" multiple class="hidden" @change="onFileSelect" />
                <span class="text-xs px-3 py-1.5 border border-border rounded-lg text-text-body hover:border-accent/60 transition-colors">+ 选择照片（最多 20 张）</span>
              </label>
            </div>
            <div v-if="!uploadedFiles.length" class="border-2 border-dashed border-border rounded-xl p-6 text-center">
              <p class="text-sm text-text-light">JPG / PNG / WebP / HEIC，每张最大 20MB</p>
            </div>
            <div v-else class="flex flex-wrap gap-1.5">
              <div v-for="(f, i) in uploadedFiles" :key="i"
                class="flex items-center gap-1.5 bg-page-bg border border-border rounded-lg px-2.5 py-1 text-xs">
                <span class="max-w-[150px] truncate text-text-body">{{ f.name }}</span>
                <button class="text-red-400 hover:text-red-600 font-bold" @click="removeFile(i)">✕</button>
              </div>
            </div>
          </template>

          <!-- ── URL 导入模式 ── -->
          <template v-else>
            <div>
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-bold text-text-heading">粘贴照片 URL</h3>
                <span class="text-xs text-text-light">
                  已解析 <strong class="text-text-heading">{{ parsedUrls.length }}</strong> / 20 条
                </span>
              </div>
              <textarea
                v-model="urlText"
                rows="5"
                class="w-full border border-border rounded-xl px-3 py-2.5 text-xs font-mono text-text-body bg-page-bg focus:border-accent outline-none resize-none leading-relaxed"
                placeholder="每行一个 URL，也支持逗号或空格分隔，最多 20 条&#10;&#10;例如：&#10;https://pic.naddsports.com/wx_applet/17783863658585563456.jpg&#10;https://pic.naddsports.com/wx_applet/17783863658585563457.jpg"
              />
              <!-- 解析预览 -->
              <div v-if="parsedUrls.length" class="mt-2 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                <span
                  v-for="(u, i) in parsedUrls" :key="i"
                  class="text-[10px] bg-accent/8 border border-accent/20 text-accent rounded px-2 py-0.5 font-mono max-w-[280px] truncate"
                  :title="u"
                >
                  {{ u.split('/').pop()?.split('?')[0] || u }}
                </span>
              </div>
              <!-- URL 下载错误 -->
              <div v-if="urlErrors.length" class="mt-2 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
                <p class="text-xs font-medium text-orange-700 mb-1">{{ urlErrors.length }} 条 URL 失败：</p>
                <ul class="space-y-0.5">
                  <li v-for="e in urlErrors" :key="e.url" class="text-[10px] text-orange-600 font-mono truncate">
                    {{ e.url.split('/').pop() }} — {{ e.error }}
                  </li>
                </ul>
              </div>
            </div>
          </template>

          <!-- 错误提示 -->
          <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
            {{ errorMsg }}
          </div>

          <!-- 操作栏 -->
          <div class="flex items-center gap-3">
            <Button
              v-if="inputMode === 'file'"
              variant="primary" :disabled="!uploadedFiles.length" :loading="running"
              @click="runValidation"
            >
              开始验证识别
            </Button>
            <Button
              v-else
              variant="primary" :disabled="!parsedUrls.length" :loading="running"
              @click="runValidationFromUrls"
            >
              开始识别（{{ parsedUrls.length }} 张）
            </Button>
            <label class="flex items-center gap-1.5 text-xs text-text-body cursor-pointer select-none">
              <input type="checkbox" v-model="showRejected" class="accent-accent" />
              显示被过滤框
            </label>
          </div>
        </div>
      </Card>

      <!-- 结果区 -->
      <div v-if="results.length" class="grid grid-cols-1 lg:grid-cols-3 gap-5">

        <!-- 左：缩略图列表 + 精度 -->
        <div class="flex flex-col gap-2">
          <p class="text-xs font-medium text-text-light px-1">识别结果（{{ results.length }} 张）</p>
          <div class="flex flex-col gap-1.5 max-h-[560px] overflow-y-auto pr-1">
            <button
              v-for="(r, i) in results" :key="i"
              class="text-left border rounded-xl p-3 transition-colors w-full"
              :class="[
                activeIdx === i ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/40',
                r.error ? 'opacity-60' : ''
              ]"
              @click="activeIdx = i"
            >
              <div class="flex items-center justify-between gap-2 mb-1">
                <span class="text-xs font-medium text-text-heading truncate max-w-[160px]">{{ r.filename }}</span>
                <span v-if="r.error" class="text-xs text-red-500">错误</span>
                <span v-else class="text-xs font-bold text-text-heading">{{ r.detected_count }} 人</span>
              </div>
              <div v-if="r.source_url" class="text-[10px] text-accent/70 truncate mb-0.5" :title="r.source_url">
                🔗 {{ r.source_url.split('/').pop()?.split('?')[0] }}
              </div>
              <div class="flex gap-3 text-xs text-text-light">
                <span>原始 {{ r.raw_count }}</span>
                <span v-if="r.rejected_boxes">过滤 {{ r.rejected_boxes.length }}</span>
              </div>
              <!-- 实际人数 -->
              <div v-if="!r.error" class="flex items-center gap-2 mt-2" @click.stop>
                <span class="text-xs text-text-light flex-shrink-0">实际人数：</span>
                <input
                  type="number" min="0"
                  class="w-14 text-xs border border-border rounded px-1.5 py-0.5 text-center focus:border-accent outline-none"
                  :value="r.ground_truth ?? ''"
                  @input="e => { r.ground_truth = (e.target as HTMLInputElement).value === '' ? null : Number((e.target as HTMLInputElement).value) }"
                  placeholder="—"
                />
                <span v-if="r.ground_truth != null" class="text-xs font-bold" :class="diffClass(r)">
                  差 {{ diffLabel(r) }}
                </span>
              </div>
              <!-- 样本状态 -->
              <div v-if="r.sample_saved" class="mt-1.5 text-[10px] text-green-600 font-medium">✓ 已保存为训练样本</div>
            </button>
          </div>

          <!-- 精度统计 -->
          <div v-if="accuracyStats" class="mt-2 border border-border rounded-xl p-3 bg-page-bg">
            <p class="text-xs font-bold text-text-heading mb-2">精度统计（{{ accuracyStats.count }} 张已标注）</p>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div><p class="text-lg font-bold text-accent">{{ accuracyStats.mae }}</p><p class="text-[10px] text-text-light">MAE</p></div>
              <div><p class="text-lg font-bold text-accent">{{ accuracyStats.exactAcc }}%</p><p class="text-[10px] text-text-light">完全准确</p></div>
              <div><p class="text-lg font-bold text-accent">{{ accuracyStats.within1Acc }}%</p><p class="text-[10px] text-text-light">误差 ≤1</p></div>
            </div>
          </div>
          <p v-else class="text-xs text-text-light px-1 mt-1">填写「实际人数」后显示精度统计</p>
        </div>

        <!-- 右：标注图 + 框明细 + 训练样本操作 -->
        <div class="lg:col-span-2 flex flex-col gap-3" v-if="activeResult">

          <!-- 标注图 -->
          <div class="border border-border rounded-xl overflow-hidden bg-black">
            <img
              v-if="activeResult.annotated_image_b64"
              :src="'data:image/jpeg;base64,' + activeResult.annotated_image_b64"
              class="w-full object-contain max-h-[380px]"
              :alt="activeResult.filename"
            />
            <div v-else-if="activeResult.error" class="p-6 text-sm text-red-400 text-center">{{ activeResult.error }}</div>
          </div>

          <!-- 图例 -->
          <div class="flex items-center gap-4 text-xs text-text-light px-1 flex-wrap">
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm border-2 border-[#FF6B35] inline-block"></span> 有效框</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm border-2 border-[#FFC300] inline-block"></span> 边缘框</span>
            <span v-if="showRejected" class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm border-2 border-[#AAAAAA] inline-block"></span> 被过滤框</span>
          </div>

          <!-- 框明细 + 训练样本操作 -->
          <div class="border border-border rounded-xl overflow-hidden">
            <div class="bg-page-bg px-4 py-2.5 flex items-center justify-between gap-2 flex-wrap">
              <span class="text-xs font-medium text-text-body">
                已确认框 {{ activeResult.confirmed_boxes.length }} 个
                <span v-if="activeResult.rejected_boxes?.length" class="text-text-light">
                  / 被过滤 {{ activeResult.rejected_boxes.length }} 个
                </span>
              </span>
              <!-- 保存为训练样本 -->
              <button
                v-if="!activeResult.error"
                class="text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors"
                :class="activeResult.sample_saved
                  ? 'border-green-300 bg-green-50 text-green-700'
                  : 'border-accent bg-accent/5 text-accent hover:bg-accent/15'"
                :disabled="savingIdx !== null"
                @click="saveSample(activeResult, activeIdx!)"
              >
                {{ savingIdx === activeIdx ? '保存中…' : activeResult.sample_saved ? '✓ 已保存' : '↓ 保存为训练样本' }}
              </button>
            </div>

            <div class="max-h-[240px] overflow-y-auto">
              <table class="w-full text-xs">
                <thead class="bg-page-bg sticky top-0">
                  <tr>
                    <th class="px-3 py-1.5 text-left text-text-light font-medium">类型</th>
                    <th class="px-3 py-1.5 text-center text-text-light font-medium">置信度</th>
                    <th class="px-3 py-1.5 text-left text-text-light font-medium">说明 / 原因</th>
                    <th class="px-3 py-1.5 text-center text-text-light font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <!-- 已确认框（可移除） -->
                  <tr v-for="(b, i) in activeResult.confirmed_boxes" :key="'v' + i" class="border-t border-border">
                    <td class="px-3 py-1.5">
                      <span class="px-1.5 py-0.5 rounded-full text-[10px]" :class="b.edge_flag ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'">
                        {{ b.edge_flag ? '边缘' : '有效' }}
                      </span>
                    </td>
                    <td class="px-3 py-1.5 text-center font-mono">{{ b.conf }}</td>
                    <td class="px-3 py-1.5 text-text-light">
                      ({{ Math.round(b.x1) }}, {{ Math.round(b.y1) }})→({{ Math.round(b.x2) }}, {{ Math.round(b.y2) }})
                    </td>
                    <td class="px-3 py-1.5 text-center">
                      <button class="text-red-400 hover:text-red-600 text-xs" @click="removeConfirmedBox(activeResult, i)" title="从训练标注中移除">移除</button>
                    </td>
                  </tr>

                  <!-- 被过滤框（可加回） -->
                  <template v-if="showRejected && activeResult.rejected_boxes?.length">
                    <tr v-for="(b, i) in activeResult.rejected_boxes" :key="'r' + i" class="border-t border-border bg-gray-50">
                      <td class="px-3 py-1.5">
                        <span class="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-100 text-gray-500">已过滤</span>
                      </td>
                      <td class="px-3 py-1.5 text-center font-mono text-gray-400">{{ b.conf }}</td>
                      <td class="px-3 py-1.5 text-gray-400 text-[10px] max-w-[200px] truncate">{{ b.rejected_reason }}</td>
                      <td class="px-3 py-1.5 text-center">
                        <button class="text-accent hover:text-accent text-xs opacity-80 hover:opacity-100" @click="addRejectedBox(activeResult, b)" title="认为这个框是正确的，加入训练标注">加回</button>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 操作提示 -->
          <div class="text-xs text-text-light bg-page-bg rounded-lg px-3 py-2.5 leading-relaxed">
            <strong class="text-text-body">如何使用训练样本功能：</strong>
            确认当前检测框是否准确，可移除误检框或将被过滤的漏检框「加回」，然后点击「保存为训练样本」。
            积累 50～200 张后，在「训练样本库」Tab 中导出数据集，再用 <code class="bg-border/40 rounded px-1">yolo train</code> 微调模型。
          </div>
        </div>

        <div v-else class="lg:col-span-2 flex items-center justify-center h-64 border border-dashed border-border rounded-xl text-sm text-text-light">
          ← 左侧点击一张图片查看详情
        </div>
      </div>

    </template>

    <!-- ═══════════════ TAB: 训练样本库 ═══════════════ -->
    <template v-else-if="activeTab === 'samples'">
      <Card>
        <div class="flex flex-col gap-5">
          <div class="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 class="text-sm font-bold text-text-heading">训练样本库</h3>
              <p class="text-xs text-text-light mt-0.5">已积累 <strong class="text-text-heading">{{ samples.length }}</strong> 张标注样本</p>
            </div>
            <div class="flex items-center gap-2">
              <Button variant="secondary" size="small" :loading="samplesLoading" @click="loadSamples">刷新</Button>
              <Button
                variant="primary"
                size="small"
                :disabled="!samples.length"
                :loading="exporting"
                @click="exportDataset"
              >
                导出 YOLO 数据集 (zip)
              </Button>
            </div>
          </div>

          <!-- 训练流程说明 -->
          <div class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-800 leading-relaxed">
            <strong>微调流程：</strong>
            ① 在「验证与调参」Tab 上传照片 → ② 确认/修正检测框 → ③ 保存为训练样本（重复直到积累 50+ 张）
            → ④ 点「导出数据集」下载 zip → ⑤ 解压后运行训练命令 → ⑥ 将 <code class="bg-amber-100 rounded px-1">best.pt</code> 替换 <code class="bg-amber-100 rounded px-1">backend/yolov8n.pt</code> → ⑦ 重启后端生效
            <br/><br/>
            <strong>训练命令（导出的 zip 内含 README.md 有完整说明）：</strong><br/>
            <code class="bg-amber-100 rounded px-1 py-0.5 block mt-1 font-mono">
              yolo train model=yolov8n.pt data=dataset/data.yaml epochs=50 imgsz=640 batch=8 patience=10
            </code>
          </div>

          <!-- 样本列表 -->
          <div v-if="!samples.length" class="text-sm text-text-light py-8 text-center">
            暂无样本。在「验证与调参」Tab 保存样本后会显示在这里。
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left text-text-light font-medium">原始文件名</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">标注人数</th>
                  <th class="px-3 py-2 text-left text-text-light font-medium">备注</th>
                  <th class="px-3 py-2 text-left text-text-light font-medium">保存时间</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in samples" :key="s.filename" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2 text-text-body max-w-[200px] truncate">{{ s.original_name }}</td>
                  <td class="px-3 py-2 text-center font-bold text-text-heading">{{ s.person_count }}</td>
                  <td class="px-3 py-2 text-text-light max-w-[150px] truncate">{{ s.note || '—' }}</td>
                  <td class="px-3 py-2 text-text-light">{{ s.saved_at?.slice(0, 16) }}</td>
                  <td class="px-3 py-2 text-center">
                    <button
                      class="text-red-400 hover:text-red-600 transition-colors"
                      :disabled="deletingFile === s.filename"
                      @click="deleteSample(s.filename)"
                    >
                      {{ deletingFile === s.filename ? '…' : '删除' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 数据分布统计 -->
          <div v-if="samples.length" class="border border-border rounded-xl p-4 bg-page-bg">
            <p class="text-xs font-medium text-text-body mb-3">标注分布</p>
            <div class="flex items-end gap-1 h-16">
              <template v-for="n in 11" :key="n">
                <div
                  class="flex-1 bg-accent/70 rounded-t-sm transition-all"
                  :style="{
                    height: Math.max(4, (samples.filter(s => s.person_count >= (n-1)*2 && s.person_count < n*2).length / samples.length) * 64) + 'px'
                  }"
                  :title="`${(n-1)*2}~${n*2-1} 人: ${samples.filter(s => s.person_count >= (n-1)*2 && s.person_count < n*2).length} 张`"
                ></div>
              </template>
            </div>
            <div class="flex justify-between text-[10px] text-text-light mt-1 px-0.5">
              <span>0人</span><span>10人</span><span>20人</span>
            </div>
          </div>

        </div>
      </Card>
    </template>

  </div>
</template>
