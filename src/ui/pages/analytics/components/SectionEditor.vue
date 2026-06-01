<script setup lang="ts">
import { ref, watch } from 'vue'
import { campusReportApi, type Section } from '@/services/campusReportApi'

const props = defineProps<{ schoolId: string; section: Section }>()
const emit = defineEmits<{ updated: [section: Section] }>()

const title = ref(props.section.title)
const content = ref(props.section.content)
const images = ref<string[]>([...props.section.images])

let saveTimer: ReturnType<typeof setTimeout> | null = null
const saving = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')

// Preview / lightbox
const previewUrl = ref<string | null>(null)

// Upload state
const uploading = ref(false)
const uploadError = ref('')

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 1000)
}

async function save() {
  saving.value = true
  saveStatus.value = 'saving'
  try {
    const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
      title: title.value,
      content: content.value,
    })
    updated.images = images.value
    emit('updated', updated)
    saveStatus.value = 'saved'
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } finally {
    saving.value = false
  }
}

async function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return
  uploadError.value = ''
  uploading.value = true
  try {
    for (const file of files) {
      const result = await campusReportApi.uploadImage(props.schoolId, file)
      images.value.push(result.filename)
    }
    const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
      images: images.value,
    })
    updated.images = images.value
    emit('updated', updated)
  } catch (err: any) {
    uploadError.value = err.message
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function removeImage(filename: string) {
  if (!confirm('确认删除这张图片？')) return
  await campusReportApi.deleteImage(props.schoolId, filename)
  images.value = images.value.filter(f => f !== filename)
  const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
    images: images.value,
  })
  updated.images = images.value
  emit('updated', updated)
}

watch(() => props.section, (s) => {
  title.value = s.title
  content.value = s.content
  images.value = [...s.images]
}, { deep: true })
</script>

<template>
  <div class="flex flex-col h-full p-4 overflow-y-auto">
    <!-- Save status -->
    <div class="flex justify-end mb-2 h-4">
      <span v-if="saveStatus === 'saving'" class="text-[10px] text-text-light">保存中…</span>
      <span v-else-if="saveStatus === 'saved'" class="text-[10px] text-accent">✓ 已保存</span>
    </div>

    <!-- Title -->
    <input
      v-model="title"
      @input="scheduleSave"
      placeholder="板块标题"
      class="w-full text-[18px] font-semibold text-text-heading bg-transparent border-none outline-none placeholder-placeholder-dk mb-3"
    />

    <!-- Content -->
    <textarea
      v-model="content"
      @input="scheduleSave"
      placeholder="在此输入内容…"
      rows="8"
      class="w-full flex-1 text-[13px] text-text-body bg-transparent border-none outline-none resize-none placeholder-placeholder-dk leading-relaxed"
    />

    <!-- Divider -->
    <div class="border-t border-border my-4" />

    <!-- Images section -->
    <div>
      <div class="text-[11px] text-text-light mb-2 font-medium">图片</div>

      <!-- Image grid -->
      <div class="flex flex-wrap gap-2">
        <div
          v-for="filename in images"
          :key="filename"
          class="relative group w-[100px] h-[75px] rounded-lg overflow-hidden border border-border bg-placeholder cursor-pointer"
          @click="previewUrl = campusReportApi.imageUrl(schoolId, filename)"
        >
          <img
            :src="campusReportApi.imageUrl(schoolId, filename)"
            class="w-full h-full object-cover"
          />
          <!-- Delete overlay -->
          <div
            class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
            @click.stop="removeImage(filename)"
          >
            <span class="text-white text-[11px] bg-red-500/80 rounded px-1.5 py-0.5">删除</span>
          </div>
        </div>

        <!-- Upload button -->
        <label
          class="w-[100px] h-[75px] rounded-lg border border-dashed border-border flex flex-col items-center justify-center cursor-pointer hover:border-accent hover:bg-accent-light/30 transition-colors"
          :class="{ 'opacity-50 pointer-events-none': uploading }"
        >
          <span class="text-[20px] text-text-light">＋</span>
          <span class="text-[10px] text-text-light mt-0.5">{{ uploading ? '上传中…' : '上传图片' }}</span>
          <input
            type="file"
            accept="image/*"
            multiple
            class="hidden"
            @change="handleFileInput"
          />
        </label>
      </div>

      <div v-if="uploadError" class="mt-1.5 text-[11px] text-red-500">{{ uploadError }}</div>
    </div>
  </div>

  <!-- Lightbox -->
  <Teleport to="body">
    <div
      v-if="previewUrl"
      class="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-8"
      @click="previewUrl = null"
    >
      <img
        :src="previewUrl"
        class="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
        @click.stop
      />
      <button
        @click="previewUrl = null"
        class="absolute top-4 right-4 text-white text-2xl hover:text-gray-300"
      >✕</button>
    </div>
  </Teleport>
</template>
