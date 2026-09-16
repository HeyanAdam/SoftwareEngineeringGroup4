<template>
  <el-card class="chat-card" shadow="never" :body-style="{ padding: '0' }">
    <div class="chat">
      <!-- 左侧会话列表 -->
      <aside class="session-panel">
        <div class="session-header">
          <span class="session-title">会话列表</span>
          <el-button type="primary" size="small" :loading="creating" @click="handleCreateSession">
            <el-icon><Plus /></el-icon>
            新建
          </el-button>
        </div>

        <el-scrollbar class="session-scroll">
          <div
            v-for="item in sessions"
            :key="item.id"
            class="session-item"
            :class="{ active: item.id === activeSessionId }"
            @click="handleSelectSession(item.id)"
          >
            <div class="session-info">
              <div class="session-name">{{ item.title || '新会话' }}</div>
              <div class="session-meta">{{ item.message_count }} 条 · {{ formatDate(item.updated_at) }}</div>
            </div>
            <el-button
              class="session-delete"
              link
              type="danger"
              @click.stop="handleDeleteSession(item)"
            >
              删除
            </el-button>
          </div>

          <el-empty
            v-if="sessions.length === 0 && !sessionLoading"
            description="还没有会话，点击「新建」开始"
            :image-size="70"
          />
        </el-scrollbar>
      </aside>

      <!-- 右侧对话区 -->
      <section class="message-panel">
        <header class="message-header">
          <span class="message-title">{{ activeSession?.title || 'AI 问答' }}</span>
          <span v-if="activeSession" class="message-sub">共 {{ activeSession.message_count }} 条消息</span>
        </header>

        <div class="message-body">
          <div v-if="messageLoading" class="message-loading">正在加载消息…</div>

          <el-empty
            v-else-if="messages.length === 0"
            description="开始你的第一个问题吧，例如：帮我制定三个月的数学复习计划"
          />

          <div
            v-for="message in messages"
            v-else
            :key="message.id"
            class="message-row"
            :class="message.role === 'user' ? 'is-user' : 'is-assistant'"
          >
            <div class="bubble" :class="message.role === 'user' ? 'bubble-user' : 'bubble-ai'">
              <div class="bubble-content">{{ message.content }}</div>
              <div class="bubble-time">{{ formatDateTime(message.created_at) }}</div>
            </div>
          </div>

          <!-- 等待 AI 回复时的提示 -->
          <div v-if="sending" class="message-row is-assistant">
            <div class="bubble bubble-ai">
              <div class="bubble-content typing">AI 正在思考…</div>
            </div>
          </div>
        </div>

        <footer class="message-footer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="3"
            resize="none"
            maxlength="2000"
            show-word-limit
            placeholder="输入你的问题，Enter 发送，Shift + Enter 换行"
            :disabled="sending"
            @keydown.enter="handleEnter"
          />
          <div class="footer-actions">
            <el-button type="primary" :loading="sending" :disabled="!canSend" @click="handleSend">
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </footer>
      </section>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Promotion } from '@element-plus/icons-vue'
import {
  createSession,
  deleteSession,
  listMessages,
  listSessions,
  sendMessage,
} from '@/api/chat'
import type { ChatMessage, ChatSession } from '@/types/chat'

/** 本地临时消息需要负数 id（后端返回的是正数），用于乐观更新列表 */
let tempMessageId = 0

const sessions = ref<ChatSession[]>([])
const activeSessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const input = ref('')
const sessionLoading = ref(false)
const messageLoading = ref(false)
const sending = ref(false)
const creating = ref(false)

/** 当前会话对象 */
const activeSession = computed<ChatSession | undefined>(() =>
  sessions.value.find((item) => item.id === activeSessionId.value),
)

/** 是否允许发送：有会话、内容非空、且不在发送中 */
const canSend = computed(
  () => activeSessionId.value !== null && input.value.trim().length > 0 && !sending.value,
)

/** ISO 时间字符串 -> 本地日期 */
function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('zh-CN')
}

/** ISO 时间字符串 -> 本地日期时间（消息气泡用，只显示时分） */
function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

/** 加载指定会话的消息；skipWhenLoaded 用于避免首次自动选中时重复请求 */
async function loadMessages(sessionId: number, skipWhenLoaded = false): Promise<void> {
  if (skipWhenLoaded && activeSessionId.value === sessionId && messages.value.length > 0) return
  messageLoading.value = true
  try {
    messages.value = await listMessages(sessionId)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    messageLoading.value = false
  }
}

/** 切换会话 */
function handleSelectSession(sessionId: number): void {
  if (sessionId === activeSessionId.value) return
  activeSessionId.value = sessionId
  messages.value = []
  void loadMessages(sessionId)
}

/** 加载会话列表；如果没有会话就自动建一个，保证右侧可以直接提问 */
async function loadSessions(): Promise<void> {
  sessionLoading.value = true
  try {
    const list = await listSessions()
    sessions.value = list
    const first = list[0]
    if (first) {
      activeSessionId.value = first.id
      await loadMessages(first.id)
    } else {
      await handleCreateSession()
    }
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    sessionLoading.value = false
  }
}

/** 新建会话 */
async function handleCreateSession(): Promise<void> {
  if (creating.value) return
  creating.value = true
  try {
    const session = await createSession({})
    sessions.value = [session, ...sessions.value]
    activeSessionId.value = session.id
    messages.value = []
    input.value = ''
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    creating.value = false
  }
}

/** 删除会话（二次确认） */
async function handleDeleteSession(session: ChatSession): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除会话「${session.title || '新会话'}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    // 用户取消
    return
  }

  try {
    await deleteSession(session.id)
  } catch {
    // 错误提示已由拦截器统一处理
    return
  }
  ElMessage.success('已删除')

  // 本地移除，避免为了一次删除再拉一遍列表
  sessions.value = sessions.value.filter((item) => item.id !== session.id)
  if (activeSessionId.value === session.id) {
    const next = sessions.value[0]
    activeSessionId.value = next ? next.id : null
    messages.value = []
    if (next) {
      await loadMessages(next.id)
    }
  }
}

/** 发送消息：先把用户消息乐观插入，再用后端返回替换（失败时回滚） */
async function handleSend(): Promise<void> {
  const sessionId = activeSessionId.value
  const content = input.value.trim()
  if (sessionId === null || content.length === 0 || sending.value) return

  tempMessageId -= 1
  const tempId = tempMessageId
  const tempMessage: ChatMessage = {
    id: tempId,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  }
  messages.value = [...messages.value, tempMessage]
  input.value = ''
  sending.value = true

  try {
    const res = await sendMessage(sessionId, { content })
    // 过滤掉临时消息，避免与后端返回的正式消息重复
    const rest = messages.value.filter((item) => item.id !== tempId)
    messages.value = [...rest, res.user_message, res.assistant_message]
    // 首条消息会由后端生成标题，这里同步刷新列表（失败也不影响对话）
    try {
      sessions.value = await listSessions()
    } catch {
      // 忽略列表刷新失败
    }
  } catch {
    // 发送失败：移除乐观插入的消息，并把内容还给输入框
    messages.value = messages.value.filter((item) => item.id !== tempId)
    input.value = content
  } finally {
    sending.value = false
  }
}

/** 回车发送，Shift + Enter 换行 */
function handleEnter(event: KeyboardEvent): void {
  if (event.shiftKey) return
  // 中文输入法组合状态下不发送（isComposing 是标准 KeyboardEvent 属性）
  if (event.isComposing) return
  event.preventDefault()
  if (canSend.value) {
    void handleSend()
  }
}

onMounted(() => {
  void loadSessions()
})
</script>

<style scoped lang="scss">
.chat-card {
  border-radius: 8px;
}

.chat {
  display: flex;
  height: calc(100vh - 140px);
  min-height: 480px;
}

.session-panel {
  display: flex;
  flex-direction: column;
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid #ebeef5;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
}

.session-title {
  font-size: 14px;
  font-weight: 600;
}

.session-scroll {
  flex: 1;
  min-height: 0;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fa;

  &:hover {
    background-color: #f5f7fa;

    .session-delete {
      visibility: visible;
    }
  }

  &.active {
    background-color: #ecf5ff;
  }
}

.session-info {
  min-width: 0;
}

.session-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.session-delete {
  visibility: hidden;
  flex-shrink: 0;

  .session-item.active & {
    visibility: visible;
  }
}

.message-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.message-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.message-title {
  font-size: 14px;
  font-weight: 600;
}

.message-sub {
  font-size: 12px;
  color: #909399;
}

.message-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  background-color: #fafafa;
}

.message-loading {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 20px 0;
}

.message-row {
  display: flex;
  margin-bottom: 14px;

  &.is-user {
    justify-content: flex-end;
  }

  &.is-assistant {
    justify-content: flex-start;
  }
}

.bubble {
  max-width: 72%;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.bubble-user {
  background-color: #409eff;
  color: #fff;
  border-top-right-radius: 2px;
}

.bubble-ai {
  background-color: #fff;
  border: 1px solid #ebeef5;
  border-top-left-radius: 2px;
}

.bubble-time {
  margin-top: 4px;
  font-size: 11px;
  opacity: 0.7;
  text-align: right;
}

.typing {
  color: #909399;
}

.message-footer {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  background-color: #fff;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>
