<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import Chip from '@/ui/components/common/Chip.vue'
import { databaseApi } from '@/services/databaseApi'

const emit = defineEmits<{
  connected: [info: { db_type: string; display_name: string; connection_type: string }]
  close: []
}>()

// ── saved connections ──
interface SavedConn {
  id: string
  name: string
  tab: 'local' | 'ssh'
  // local fields
  localDbType?: string
  localPath?: string
  localHost?: string
  localPort?: string
  localDb?: string
  localUser?: string
  localPass?: string
  // ssh fields
  sshHost?: string
  sshPort?: string
  sshUser?: string
  sshAuthMode?: string
  sshPassword?: string
  sshKey?: string
  sshDbType?: string
  sshDbHost?: string
  sshDbPort?: string
  sshDbName?: string
  sshDbUser?: string
  sshDbPass?: string
}

const STORAGE_KEY = 'db_saved_connections'
const savedConns = ref<SavedConn[]>([])
const saveNameInput = ref('')
const showSavePrompt = ref(false)
const loadedFromSaved = ref(false)  // skip save prompt when reconnecting a saved config

function loadSaved() {
  try {
    savedConns.value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    savedConns.value = []
  }
}

function persistSaved() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(savedConns.value))
}

function saveCurrentConfig() {
  const name = saveNameInput.value.trim() || (activeTab.value === 'ssh' ? sshHost.value : localHost.value)
  if (!name) return
  const conn: SavedConn = {
    id: Date.now().toString(),
    name,
    tab: activeTab.value,
    localDbType: localDbType.value,
    localPath: localPath.value,
    localHost: localHost.value,
    localPort: localPort.value,
    localDb: localDb.value,
    localUser: localUser.value,
    localPass: localPass.value,
    sshHost: sshHost.value,
    sshPort: sshPort.value,
    sshUser: sshUser.value,
    sshAuthMode: sshAuthMode.value,
    sshPassword: sshPassword.value,
    sshKey: sshKey.value,
    sshDbType: sshDbType.value,
    sshDbHost: sshDbHost.value,
    sshDbPort: sshDbPort.value,
    sshDbName: sshDbName.value,
    sshDbUser: sshDbUser.value,
    sshDbPass: sshDbPass.value,
  }
  savedConns.value.unshift(conn)
  persistSaved()
  showSavePrompt.value = false
  saveNameInput.value = ''
}

function loadConn(c: SavedConn) {
  loadedFromSaved.value = true
  activeTab.value = c.tab
  localDbType.value = (c.localDbType as any) || 'sqlite'
  localPath.value = c.localPath || ''
  localHost.value = c.localHost || '127.0.0.1'
  localPort.value = c.localPort || ''
  localDb.value = c.localDb || ''
  localUser.value = c.localUser || ''
  localPass.value = c.localPass || ''
  sshHost.value = c.sshHost || ''
  sshPort.value = c.sshPort || '22'
  sshUser.value = c.sshUser || ''
  sshAuthMode.value = (c.sshAuthMode as any) || 'password'
  sshPassword.value = c.sshPassword || ''
  sshKey.value = c.sshKey || ''
  sshDbType.value = (c.sshDbType as any) || 'mysql'
  sshDbHost.value = c.sshDbHost || '127.0.0.1'
  sshDbPort.value = c.sshDbPort || ''
  sshDbName.value = c.sshDbName || ''
  sshDbUser.value = c.sshDbUser || ''
  sshDbPass.value = c.sshDbPass || ''
}

function deleteConn(id: string) {
  savedConns.value = savedConns.value.filter(c => c.id !== id)
  persistSaved()
}

onMounted(loadSaved)

// ── tab state ──
type TabKey = 'local' | 'ssh'
const activeTab = ref<TabKey>('local')

// ── local form ──
type LocalDbType = 'sqlite' | 'mysql' | 'postgres'
const localDbType = ref<LocalDbType>('sqlite')
const localPath = ref('')
const localHost = ref('127.0.0.1')
const localPort = ref('')
const localDb = ref('')
const localUser = ref('')
const localPass = ref('')

const defaultPort = computed(() => localDbType.value === 'mysql' ? '3306' : '5432')

// ── SSH form ──
type SshDbType = 'mysql' | 'postgres'
const sshHost = ref('')
const sshPort = ref('22')
const sshUser = ref('')
const sshAuthMode = ref<'password' | 'key'>('password')
const sshPassword = ref('')
const sshKey = ref('')
const sshDbType = ref<SshDbType>('mysql')
const sshDbHost = ref('127.0.0.1')
const sshDbPort = ref('')
const sshDbName = ref('')
const sshDbUser = ref('root')
const sshDbPass = ref('')

const sshDefaultPort = computed(() => sshDbType.value === 'mysql' ? '3306' : '5432')

// ── status ──
const loading = ref(false)
const errorMsg = ref('')
const pendingResult = ref<{ db_type: string; display_name: string; connection_type: string } | null>(null)

async function handleConnect() {
  errorMsg.value = ''
  loading.value = true
  try {
    let result
    if (activeTab.value === 'local') {
      result = await databaseApi.connectLocal({
        db_type: localDbType.value,
        path: localDbType.value === 'sqlite' ? localPath.value : undefined,
        host: localDbType.value !== 'sqlite' ? localHost.value : undefined,
        port: localDbType.value !== 'sqlite' && localPort.value ? parseInt(localPort.value) : undefined,
        database: localDbType.value !== 'sqlite' ? localDb.value : undefined,
        user: localDbType.value !== 'sqlite' ? localUser.value : undefined,
        password: localDbType.value !== 'sqlite' ? localPass.value : undefined,
      })
    } else {
      result = await databaseApi.connectSSH({
        ssh_host: sshHost.value,
        ssh_port: parseInt(sshPort.value) || 22,
        ssh_user: sshUser.value,
        ssh_password: sshAuthMode.value === 'password' ? sshPassword.value : undefined,
        ssh_key: sshAuthMode.value === 'key' ? sshKey.value : undefined,
        db_type: sshDbType.value,
        db_host: sshDbHost.value || '127.0.0.1',
        db_port: sshDbPort.value ? parseInt(sshDbPort.value) : undefined,
        database: sshDbName.value,
        db_user: sshDbUser.value,
        db_password: sshDbPass.value,
      })
    }
    pendingResult.value = {
      db_type: result.db_type ?? '',
      display_name: result.display_name ?? '',
      connection_type: result.connection_type ?? '',
    }
    // If loaded from a saved config, no need to prompt for saving again
    if (loadedFromSaved.value) {
      closeWithResult()
    } else {
      showSavePrompt.value = true
    }
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '连接失败'
  } finally {
    loading.value = false
  }
}

function confirmSave() {
  saveCurrentConfig()
  closeWithResult()
}

function skipSave() {
  showSavePrompt.value = false
  closeWithResult()
}

function closeWithResult() {
  if (pendingResult.value) {
    emit('connected', pendingResult.value)
  }
  emit('close')
}
</script>

<template>
  <Teleport to="body">
  <div
    class="fixed inset-0 z-[9999] flex items-center justify-center"
    style="background: rgba(61,53,48,0.35); backdrop-filter: blur(2px)"
    @click.self="emit('close')"
  >
    <div
      class="w-[520px] rounded-xl border border-border flex flex-col"
      style="background: #FEFCF8; box-shadow: 0 20px 60px rgba(61,53,48,0.18), 0 4px 12px rgba(61,53,48,0.1); max-height: min(88vh, 680px)"
    >
      <!-- header -->
      <div class="flex items-center gap-2 px-5 py-3.5 border-b border-border shrink-0">
        <span class="text-[15px] font-bold text-text-heading">连接数据库</span>
        <button
          class="ml-auto text-text-light hover:text-text-body w-6 h-6 flex items-center justify-center rounded hover:bg-chip"
          @click="emit('close')"
        >✕</button>
      </div>

      <!-- saved connections -->
      <div v-if="savedConns.length > 0" class="px-5 py-2.5 border-b border-border shrink-0">
        <div class="text-[10px] font-semibold text-text-light uppercase tracking-wider mb-1.5">已保存连接</div>
        <div class="flex flex-col gap-1 max-h-[100px] overflow-y-auto">
          <div
            v-for="c in savedConns"
            :key="c.id"
            class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border bg-page-bg hover:bg-chip cursor-pointer group transition-colors"
            @click="loadConn(c)"
          >
            <span class="text-[12px]">{{ c.tab === 'ssh' ? '🔐' : '💾' }}</span>
            <span class="flex-1 text-[12px] text-text-body font-medium truncate">{{ c.name }}</span>
            <span class="text-[10px] text-text-light shrink-0">{{ c.tab === 'ssh' ? c.sshHost : c.localHost }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 text-[11px] text-text-light hover:text-[#A0522D] px-1 transition-opacity shrink-0"
              @click.stop="deleteConn(c.id)"
            >✕</button>
          </div>
        </div>
      </div>

      <!-- tab bar -->
      <div class="flex border-b border-border shrink-0">
        <button
          class="flex-1 py-2.5 text-[13px] font-medium border-b-2 transition-colors"
          :class="activeTab === 'local'
            ? 'border-accent text-accent'
            : 'border-transparent text-text-light hover:text-text-body'"
          @click="activeTab = 'local'"
        >本地连接</button>
        <button
          class="flex-1 py-2.5 text-[13px] font-medium border-b-2 transition-colors"
          :class="activeTab === 'ssh'
            ? 'border-accent text-accent'
            : 'border-transparent text-text-light hover:text-text-body'"
          @click="activeTab = 'ssh'"
        >SSH 远程连接</button>
      </div>

      <!-- scrollable form area -->
      <div class="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0">

        <!-- LOCAL TAB -->
        <template v-if="activeTab === 'local'">
          <div>
            <div class="text-[11px] font-semibold text-text-body mb-1.5">数据库类型</div>
            <div class="flex gap-1.5">
              <Chip
                v-for="t in ['sqlite', 'mysql', 'postgres'] as LocalDbType[]"
                :key="t"
                :active="localDbType === t"
                @click="localDbType = t"
                style="font-size: 11px"
              >{{ t === 'sqlite' ? 'SQLite' : t === 'mysql' ? 'MySQL' : 'PostgreSQL' }}</Chip>
            </div>
          </div>

          <template v-if="localDbType === 'sqlite'">
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">文件路径<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <Input v-model="localPath" placeholder="/absolute/path/to/database.db" />
              <div class="text-[10px] text-text-light mt-1">输入服务器端的绝对路径</div>
            </div>
          </template>
          <template v-else>
            <div class="grid grid-cols-3 gap-2">
              <div class="col-span-2">
                <div class="text-[11px] font-semibold text-text-body mb-1">主机<span class="text-[#C17F3A] ml-0.5">*</span></div>
                <Input v-model="localHost" placeholder="127.0.0.1" />
              </div>
              <div>
                <div class="text-[11px] font-semibold text-text-body mb-1">端口</div>
                <Input v-model="localPort" :placeholder="defaultPort" />
              </div>
            </div>
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">数据库名<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <Input v-model="localDb" placeholder="database_name" />
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <div class="text-[11px] font-semibold text-text-body mb-1">用户名<span class="text-[#C17F3A] ml-0.5">*</span></div>
                <Input v-model="localUser" placeholder="root" />
              </div>
              <div>
                <div class="text-[11px] font-semibold text-text-body mb-1">密码</div>
                <Input v-model="localPass" type="password" placeholder="••••••••" />
              </div>
            </div>
          </template>
        </template>

        <!-- SSH TAB -->
        <template v-else>
          <div class="text-[11px] font-semibold text-text-light uppercase tracking-wider">SSH 服务器</div>
          <div class="grid grid-cols-3 gap-2">
            <div class="col-span-2">
              <div class="text-[11px] font-semibold text-text-body mb-1">SSH 主机<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <Input v-model="sshHost" placeholder="your.server.com" />
            </div>
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">SSH 端口</div>
              <Input v-model="sshPort" placeholder="22" />
            </div>
          </div>
          <div>
            <div class="text-[11px] font-semibold text-text-body mb-1">SSH 用户名<span class="text-[#C17F3A] ml-0.5">*</span></div>
            <Input v-model="sshUser" placeholder="ubuntu" />
          </div>
          <div>
            <div class="text-[11px] font-semibold text-text-body mb-1.5">SSH 认证方式</div>
            <div class="flex gap-1.5 mb-2">
              <Chip :active="sshAuthMode === 'password'" @click="sshAuthMode = 'password'" style="font-size: 11px">密码</Chip>
              <Chip :active="sshAuthMode === 'key'" @click="sshAuthMode = 'key'" style="font-size: 11px">私钥</Chip>
            </div>
            <template v-if="sshAuthMode === 'password'">
              <div class="text-[11px] font-semibold text-text-body mb-1">SSH 密码<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <Input v-model="sshPassword" type="password" placeholder="SSH 密码" />
            </template>
            <template v-else>
              <div class="text-[11px] font-semibold text-text-body mb-1">私钥内容<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <textarea
                v-model="sshKey"
                rows="4"
                placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;粘贴私钥内容..."
                class="w-full bg-page-bg border border-border rounded-md px-3 py-2 text-[11px] font-mono text-text-body placeholder:text-text-light outline-none resize-none focus:border-accent"
              />
            </template>
          </div>

          <div class="text-[11px] font-semibold text-text-light uppercase tracking-wider pt-1">远程数据库</div>
          <div>
            <div class="text-[11px] font-semibold text-text-body mb-1.5">数据库类型</div>
            <div class="flex gap-1.5">
              <Chip :active="sshDbType === 'mysql'" @click="sshDbType = 'mysql'" style="font-size: 11px">MySQL</Chip>
              <Chip :active="sshDbType === 'postgres'" @click="sshDbType = 'postgres'" style="font-size: 11px">PostgreSQL</Chip>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-2">
            <div class="col-span-2">
              <div class="text-[11px] font-semibold text-text-body mb-1">DB 主机（服务器内部）</div>
              <Input v-model="sshDbHost" placeholder="127.0.0.1" />
            </div>
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">DB 端口</div>
              <Input v-model="sshDbPort" :placeholder="sshDefaultPort" />
            </div>
          </div>
          <div>
            <div class="text-[11px] font-semibold text-text-body mb-1">数据库名</div>
            <Input v-model="sshDbName" placeholder="留空后可在侧边栏浏览所有数据库" />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">DB 用户名<span class="text-[#C17F3A] ml-0.5">*</span></div>
              <Input v-model="sshDbUser" placeholder="root" />
            </div>
            <div>
              <div class="text-[11px] font-semibold text-text-body mb-1">DB 密码</div>
              <Input v-model="sshDbPass" type="password" placeholder="••••••••" />
            </div>
          </div>
        </template>
      </div>

      <!-- error -->
      <div v-if="errorMsg" class="mx-5 mb-2 px-3 py-2 rounded-lg bg-[#FEF0E7] border border-[#E8C5A0] text-[11px] text-[#A0522D] shrink-0">
        {{ errorMsg }}
      </div>

      <!-- save prompt -->
      <div v-if="showSavePrompt" class="mx-5 mb-2 px-3 py-2.5 rounded-lg bg-accent-light border border-accent/30 flex items-center gap-2 shrink-0">
        <span class="text-[11px] text-accent font-semibold shrink-0">✓ 已连接，保存配置？</span>
        <input
          v-model="saveNameInput"
          :placeholder="activeTab === 'ssh' ? sshHost : localHost"
          class="flex-1 bg-white border border-accent/30 rounded px-2 py-1 text-[11px] outline-none focus:border-accent min-w-0"
          @keydown.enter="confirmSave"
        />
        <button class="text-[11px] font-semibold text-accent px-2 py-1 rounded hover:bg-accent/10 shrink-0" @click="confirmSave">保存</button>
        <button class="text-[11px] text-text-light hover:text-text-body shrink-0" @click="skipSave">跳过</button>
      </div>

      <!-- footer -->
      <div class="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-border shrink-0">
        <Button variant="secondary" @click="emit('close')">取消</Button>
        <Button variant="primary" :disabled="loading" @click="handleConnect">
          {{ loading ? '连接中…' : '连接' }}
        </Button>
      </div>
    </div>
  </div>
  </Teleport>
</template>
