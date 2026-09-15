<script setup lang="ts">
/**
 * 协作聊天: 房间列表 + 消息气泡 + 发送框 + 在线人数 + 输入中提示 + 实时通知
 * 消息收发走 WebSocket (ws store), 历史消息走 HTTP /chat/rooms/{code}/messages
 */

import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  ElAvatar,
  ElBadge,
  ElButton,
  ElEmpty,
  ElIcon,
  ElInput,
  ElScrollbar,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { Bell, ChatDotRound, Promotion, Refresh } from '@element-plus/icons-vue'

import PageContainer from '@/components/common/PageContainer.vue'
import { listMessages, listRooms } from '@/api/chat'
import { useAuthStore } from '@/stores/auth'
import { useWsStore } from '@/stores/ws'
import { formatDateTime, formatRelativeTime, initialsOf } from '@/utils/format'
import type { ChatMessage, ChatRoom } from '@/types/chat'

const authStore = useAuthStore()
const wsStore = useWsStore()

const rooms = ref<ChatRoom[]>([])
const loadingRooms = ref(false)
const loadingHistory = ref(false)
const draft = ref('')
const scrollRef = ref<InstanceType<typeof ElScrollbar>>()

const activeRoom = computed(() => wsStore.activeRoom)
const messages = computed(() => wsStore.currentMessages)
const onlineCount = computed(() => wsStore.currentOnline)
const typingUsers = computed(() => wsStore.currentTypingUsers)
const notifications = computed(() => wsStore.notifications)

/** 当前用户 id, 用于区分自己/他人的消息气泡 */
const selfId = computed(() => authStore.user?.id ?? null)

/** 消息按时间排序 (欢迎历史与实时推送可能乱序) */
const orderedMessages = computed(() =>
  [...messages.value].sort((a, b) => {
    const left = a.created_at ? new Date(a.created_at).getTime() : 0
    const right = b.created_at ? new Date(b.created_at).getTime() : 0
    return left - right
  }),
)

function isOwn(message: ChatMessage): boolean {
  return selfId.value !== null && message.sender_id === selfId.value
}

/** 滚动到底部 */
async function scrollToBottom(): Promise<void> {
  await nextTick()
  const wrap = scrollRef.value?.wrapRef
  if (wrap) wrap.scrollTop = wrap.scrollHeight
}

async function loadRooms(): Promise<void> {
  loadingRooms.value = true
  try {
    rooms.value = await listRooms()
    if (rooms.value.length && !rooms.value.some((room) => room.code === activeRoom.value)) {
      const preferred = rooms.value.find((room) => room.is_default) ?? rooms.value[0]
      if (preferred) switchRoom(preferred.code)
    }
  } finally {
    loadingRooms.value = false
  }
}

async function loadHistory(room: string): Promise<void> {
  loadingHistory.value = true
  try {
    const history = await listMessages(room, 50)
    wsStore.loadHistory(room, history)
    await scrollToBottom()
  } finally {
    loadingHistory.value = false
  }
}

function switchRoom(code: string): void {
  wsStore.switchRoom(code)
  void loadHistory(code)
}

function sendMessage(): void {
  const content = draft.value.trim()
  if (!content) return
  const queued = wsStore.sendMessage(content)
  draft.value = ''
  if (!queued) {
    // 离线时消息已入队, 连接恢复后自动补发
    return
  }
  void scrollToBottom()
}

/** 输入中提示 (节流: 每 2 秒最多发送一次) */
let lastTypingAt = 0
function handleTyping(): void {
  const now = Date.now()
  if (now - lastTypingAt < 2_000) return
  lastTypingAt = now
  wsStore.sendTyping()
}

watch(
  () => messages.value.length,
  () => {
    void scrollToBottom()
  },
)

onMounted(async () => {
  await loadRooms()
  wsStore.connect(activeRoom.value)
  await loadHistory(activeRoom.value)
  await scrollToBottom()
})
</script>

<template>
  <PageContainer title="协作聊天" description="基于 WebSocket 的实时消息与全站通知">
    <template #actions>
      <ElTag :type="wsStore.isConnected ? 'success' : 'warning'" size="small" effect="light" round>
        {{ wsStore.isConnected ? '实时已连接' : '实时未连接' }}
      </ElTag>
      <ElButton :icon="Refresh" :loading="loadingHistory" @click="loadHistory(activeRoom)">
        刷新消息
      </ElButton>
    </template>

    <div class="chat">
      <!-- 房间列表 -->
      <aside class="chat__rooms">
        <div class="chat__panel-title">
          <ElIcon><ChatDotRound /></ElIcon>
          <span>聊天室</span>
        </div>
        <ul v-loading="loadingRooms" class="chat__room-list">
          <li
            v-for="room in rooms"
            :key="room.code"
            :class="['chat__room', { 'is-active': room.code === activeRoom }]"
            @click="switchRoom(room.code)"
          >
            <div class="chat__room-main">
              <span class="chat__room-name">{{ room.name }}</span>
              <span class="chat__room-code text-mono">#{{ room.code }}</span>
            </div>
            <ElBadge
              :value="wsStore.onlineCounts[room.code] ?? 0"
              :hidden="!wsStore.onlineCounts[room.code]"
              type="success"
            />
          </li>
        </ul>
        <ElEmpty v-if="!rooms.length && !loadingRooms" description="暂无聊天室" :image-size="60" />
      </aside>

      <!-- 消息区域 -->
      <section class="chat__main">
        <header class="chat__header">
          <div>
            <span class="chat__title">
              {{ rooms.find((room) => room.code === activeRoom)?.name ?? activeRoom }}
            </span>
            <span class="chat__subtitle">
              {{ rooms.find((room) => room.code === activeRoom)?.description ?? '实时频道' }}
            </span>
          </div>
          <ElTooltip content="当前房间在线人数" placement="bottom">
            <ElTag type="success" size="small" effect="light">在线 {{ onlineCount }}</ElTag>
          </ElTooltip>
        </header>

        <ElScrollbar ref="scrollRef" class="chat__messages">
          <div v-if="!orderedMessages.length" class="chat__empty">
            <ElEmpty description="还没有消息, 来说点什么吧" :image-size="80" />
          </div>

          <div
            v-for="message in orderedMessages"
            :key="`${message.id ?? message.created_at}-${message.sender_id}`"
            :class="['chat__message', { 'is-own': isOwn(message) }]"
          >
            <ElAvatar :size="32" class="chat__avatar">
              {{ initialsOf(message.sender_name) }}
            </ElAvatar>
            <div class="chat__bubble-wrap">
              <div class="chat__meta">
                <span class="chat__sender">{{ message.sender_name }}</span>
                <span class="chat__time">{{ formatDateTime(message.created_at) }}</span>
              </div>
              <div class="chat__bubble">{{ message.content }}</div>
            </div>
          </div>
        </ElScrollbar>

        <div class="chat__typing">
          <span v-if="typingUsers.length" class="text-muted">
            {{ typingUsers.join('、') }} 正在输入…
          </span>
        </div>

        <footer class="chat__composer">
          <ElInput
            v-model="draft"
            type="textarea"
            :rows="2"
            resize="none"
            maxlength="4000"
            placeholder="输入消息, Enter 发送, Shift + Enter 换行"
            @input="handleTyping"
            @keydown.enter.exact.prevent="sendMessage"
          />
          <ElButton
            type="primary"
            :icon="Promotion"
            :disabled="!draft.trim()"
            @click="sendMessage"
          >
            发送
          </ElButton>
        </footer>
      </section>

      <!-- 右栏: 在线 + 通知 -->
      <aside class="chat__side">
        <div class="chat__panel-title">
          <ElIcon><Bell /></ElIcon>
          <span>实时通知</span>
          <ElTag v-if="wsStore.unreadCount" type="danger" size="small" effect="dark">
            {{ wsStore.unreadCount }}
          </ElTag>
        </div>

        <ul class="chat__notifications">
          <li v-for="item in notifications.slice(0, 12)" :key="item.id" class="chat__notification">
            <div class="chat__notification-title">
              <ElTag
                size="small"
                effect="light"
                :type="
                  item.level === 'error'
                    ? 'danger'
                    : item.level === 'warning'
                      ? 'warning'
                      : item.level === 'success'
                        ? 'success'
                        : 'primary'
                "
              >
                {{ item.level }}
              </ElTag>
              <span>{{ item.title }}</span>
            </div>
            <p class="chat__notification-content">{{ item.content }}</p>
            <span class="chat__time">{{ formatRelativeTime(item.receivedAt) }}</span>
          </li>
        </ul>

        <ElEmpty v-if="!notifications.length" description="暂无通知" :image-size="60" />

        <div class="chat__panel-title mt-16">
          <ElIcon><ChatDotRound /></ElIcon>
          <span>在线成员 ({{ (wsStore.onlineUsers[activeRoom] ?? []).length }})</span>
        </div>
        <ul class="chat__online">
          <li v-for="name in wsStore.onlineUsers[activeRoom] ?? []" :key="name">
            <ElAvatar :size="22">{{ initialsOf(name) }}</ElAvatar>
            <span>{{ name }}</span>
          </li>
          <li v-if="!(wsStore.onlineUsers[activeRoom] ?? []).length" class="text-muted">
            暂无其他在线成员
          </li>
        </ul>
      </aside>
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.chat {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 260px;
  gap: 14px;
  height: calc(100vh - 230px);
  min-height: 460px;

  &__rooms,
  &__side {
    display: flex;
    flex-direction: column;
    padding: 12px;
    overflow-y: auto;
    background-color: var(--app-bg-container);
    border: 1px solid var(--app-border-color-light);
    border-radius: var(--app-radius-md);
  }

  &__main {
    display: flex;
    flex-direction: column;
    min-width: 0;
    background-color: var(--app-bg-container);
    border: 1px solid var(--app-border-color-light);
    border-radius: var(--app-radius-md);
  }

  &__panel-title {
    display: flex;
    gap: 6px;
    align-items: center;
    padding-bottom: 10px;
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-primary);
    border-bottom: 1px solid var(--app-border-color-light);
  }

  &__room-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__room {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    cursor: pointer;
    border-radius: var(--app-radius-sm);
    transition: background-color 0.16s ease;

    &:hover {
      background-color: var(--app-bg-hover);
    }

    &.is-active {
      background-color: rgb(37 99 235 / 10%);
    }

    &-main {
      display: flex;
      flex-direction: column;
      line-height: 1.3;
    }

    &-name {
      font-size: 13px;
      font-weight: 600;
      color: var(--app-text-primary);
    }

    &-code {
      font-size: 11px;
      color: var(--app-text-placeholder);
    }
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--app-border-color-light);
  }

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__subtitle {
    margin-left: 8px;
    font-size: 12px;
    color: var(--app-text-placeholder);
  }

  &__messages {
    flex: 1;
    min-height: 0;
    padding: 16px;
  }

  &__empty {
    padding-top: 40px;
  }

  &__message {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;

    &.is-own {
      flex-direction: row-reverse;

      .chat__bubble-wrap {
        align-items: flex-end;
      }

      .chat__meta {
        flex-direction: row-reverse;
      }

      .chat__bubble {
        color: #fff;
        background-color: var(--app-color-primary);
      }
    }
  }

  &__avatar {
    flex-shrink: 0;
    background-color: var(--app-bg-hover);
  }

  &__bubble-wrap {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 70%;
  }

  &__meta {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 11px;
  }

  &__sender {
    font-weight: 600;
    color: var(--app-text-secondary);
  }

  &__time {
    font-size: 11px;
    color: var(--app-text-placeholder);
  }

  &__bubble {
    padding: 8px 12px;
    font-size: 13px;
    line-height: 1.55;
    color: var(--app-text-primary);
    word-break: break-word;
    white-space: pre-wrap;
    background-color: var(--app-bg-hover);
    border-radius: 10px;
  }

  &__typing {
    height: 20px;
    padding: 0 16px;
    font-size: 12px;
  }

  &__composer {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    padding: 12px 16px 16px;
    border-top: 1px solid var(--app-border-color-light);

    :deep(.el-textarea) {
      flex: 1;
    }
  }

  &__notifications {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 46%;
    overflow-y: auto;
  }

  &__notification {
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--app-border-color-light);

    &-title {
      display: flex;
      gap: 6px;
      align-items: center;
      font-size: 12px;
      font-weight: 600;
      color: var(--app-text-primary);
    }

    &-content {
      margin-top: 3px;
      font-size: 12px;
      color: var(--app-text-secondary);
    }
  }

  &__online {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
    color: var(--app-text-secondary);

    li {
      display: flex;
      gap: 6px;
      align-items: center;
    }
  }
}

@media (width <= 1180px) {
  .chat {
    grid-template-columns: 200px minmax(0, 1fr);

    &__side {
      display: none;
    }
  }
}
</style>
