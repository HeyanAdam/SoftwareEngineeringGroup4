/**
 * WebSocket 状态: 连接状态 / 在线用户 / 各房间消息 / 通知队列。
 *
 * 生命周期: connect() 在布局挂载时调用, disconnect() 在退出登录或布局卸载时调用。
 * 客户端本身带指数退避重连与离线消息队列, 这里只负责把事件映射为响应式状态。
 */

import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

import { WsClient, resolveWsUrl } from '@/utils/ws'
import { useAuthStore } from '@/stores/auth'
import type {
  ChatMessage,
  NotificationLevel,
  WsNotification,
} from '@/types/chat'
import type { ServerMessage, WsStatus } from '@/types/ws'

/** 通知最多保留条数 */
const MAX_NOTIFICATIONS = 50
/** 单个房间最多保留消息条数 */
const MAX_MESSAGES_PER_ROOM = 200
/** 正在输入提示的存活时间 (毫秒) */
const TYPING_TTL = 4_000

const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? '/ws'

/** 从 welcome 消息中取出的服务端用户摘要 */
interface WsIdentity {
  id: number
  username: string
  is_superuser: boolean
}

export const useWsStore = defineStore('ws', () => {
  const status = ref<WsStatus>('idle')
  const connectedAt = ref<number | null>(null)
  const lastError = ref<string | null>(null)
  const identity = ref<WsIdentity | null>(null)
  /** 服务端声明的房间列表 */
  const serverRooms = ref<string[]>([])
  /** 当前订阅的房间 (用于发送消息) */
  const activeRoom = ref('lobby')
  /** room -> 消息列表 */
  const messages = ref<Record<string, ChatMessage[]>>({})
  /** room -> 在线人数 */
  const onlineCounts = ref<Record<string, number>>({})
  /** room -> 在线用户名列表 */
  const onlineUsers = ref<Record<string, string[]>>({})
  /** 通知队列 (最新在前) */
  const notifications = ref<WsNotification[]>([])
  /** room -> 正在输入的用户集合 */
  const typingUsers = ref<Record<string, string[]>>({})
  /** 未读通知数 */
  const unreadCount = ref(0)

  const client = shallowRef<WsClient | null>(null)
  const typingTimers = new Map<string, ReturnType<typeof setTimeout>>()

  /* ------------------------------ getters ------------------------------ */
  const isConnected = computed(() => status.value === 'open')
  const currentMessages = computed<ChatMessage[]>(() => messages.value[activeRoom.value] ?? [])
  const currentOnline = computed(() => onlineCounts.value[activeRoom.value] ?? 0)
  const currentTypingUsers = computed(() => typingUsers.value[activeRoom.value] ?? [])

  /* ------------------------------ 内部工具 ------------------------------ */

  function pushNotification(level: NotificationLevel, title: string, content: string): void {
    notifications.value.unshift({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      level,
      title,
      content,
      receivedAt: Date.now(),
      read: false,
    })
    if (notifications.value.length > MAX_NOTIFICATIONS) {
      notifications.value.length = MAX_NOTIFICATIONS
    }
    unreadCount.value += 1
  }

  /** 追加消息, 按 id 去重 (历史消息与实时推送可能重叠) */
  function appendMessage(room: string, message: ChatMessage): void {
    const list = messages.value[room] ?? []
    if (message.id !== null && list.some((item) => item.id === message.id)) return
    list.push(message)
    if (list.length > MAX_MESSAGES_PER_ROOM) {
      list.splice(0, list.length - MAX_MESSAGES_PER_ROOM)
    }
    messages.value = { ...messages.value, [room]: list }
  }

  function markTyping(room: string, username: string): void {
    const list = typingUsers.value[room] ?? []
    if (!list.includes(username)) {
      typingUsers.value = { ...typingUsers.value, [room]: [...list, username] }
    }
    const timerKey = `${room}:${username}`
    const existing = typingTimers.get(timerKey)
    if (existing) clearTimeout(existing)
    typingTimers.set(
      timerKey,
      setTimeout(() => {
        typingUsers.value = {
          ...typingUsers.value,
          [room]: (typingUsers.value[room] ?? []).filter((item) => item !== username),
        }
        typingTimers.delete(timerKey)
      }, TYPING_TTL),
    )
  }

  /** 处理服务端消息, 映射为状态变更 */
  function handleServerMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'welcome': {
        identity.value = message.user
        serverRooms.value = message.rooms ?? []
        break
      }
      case 'chat': {
        appendMessage(message.room, message.message)
        break
      }
      case 'presence': {
        onlineCounts.value = { ...onlineCounts.value, [message.room]: message.online }
        onlineUsers.value = { ...onlineUsers.value, [message.room]: message.users ?? [] }
        break
      }
      case 'notification': {
        // 后端把"正在输入"也放在 notification 中 (title === 'typing')
        if (message.title === 'typing') {
          const username = message.content.replace(/\s*正在输入\.*$/, '').trim()
          if (username) markTyping(message.room ?? activeRoom.value, username)
          break
        }
        pushNotification(message.level, message.title, message.content)
        break
      }
      case 'error': {
        lastError.value = message.content
        pushNotification('error', '操作失败', message.content)
        break
      }
      default:
        break
    }
  }

  /* ------------------------------ actions ------------------------------ */

  /** 建立连接 (重复调用为空操作) */
  function connect(room?: string): void {
    if (room) activeRoom.value = room
    if (client.value) {
      client.value.connect()
      return
    }
    const auth = useAuthStore()
    const wsClient = new WsClient({
      urlFactory: () =>
        resolveWsUrl(WS_BASE, auth.accessToken ?? null, activeRoom.value),
    })

    wsClient.on('open', () => {
      status.value = 'open'
      connectedAt.value = Date.now()
      lastError.value = null
    })
    wsClient.on('close', () => {
      status.value = 'closed'
      connectedAt.value = null
    })
    wsClient.on('error', () => {
      lastError.value = 'WebSocket 连接异常, 正在重试…'
    })
    wsClient.on('message', (message) => {
      handleServerMessage(message as ServerMessage)
    })
    wsClient.on('heartbeat', () => {
      // 心跳正常, 保持 open 状态
      if (status.value !== 'open') status.value = 'open'
    })

    status.value = 'connecting'
    client.value = wsClient
    wsClient.connect()
  }

  /** 主动断开并停止重连 */
  function disconnect(): void {
    client.value?.close()
    client.value = null
    status.value = 'closed'
    connectedAt.value = null
    identity.value = null
    for (const timer of typingTimers.values()) clearTimeout(timer)
    typingTimers.clear()
  }

  /** 切换房间: 先离开旧房间再加入新房间 */
  function switchRoom(room: string): void {
    if (room === activeRoom.value) return
    const previous = activeRoom.value
    client.value?.send({ type: 'leave', room: previous })
    activeRoom.value = room
    client.value?.joinRoom(room)
  }

  /** 发送聊天消息 (离线时自动入队) */
  function sendMessage(content: string, room?: string): boolean {
    const text = content.trim()
    if (!text) return false
    return client.value?.sendChat(room ?? activeRoom.value, text) ?? false
  }

  /** 广播"正在输入" */
  function sendTyping(room?: string): void {
    client.value?.sendTyping(room ?? activeRoom.value)
  }

  /** 载入历史消息 (页面首次进入房间时调用) */
  function loadHistory(room: string, list: ChatMessage[]): void {
    if (!list.length) return
    for (const item of list) appendMessage(room, item)
  }

  /** 清空某个房间的消息 */
  function clearRoom(room: string): void {
    messages.value = { ...messages.value, [room]: [] }
  }

  /** 全部标记为已读 */
  function markNotificationsRead(): void {
    unreadCount.value = 0
    notifications.value = notifications.value.map((item) => ({ ...item, read: true }))
  }

  /** 清空通知 */
  function clearNotifications(): void {
    notifications.value = []
    unreadCount.value = 0
  }

  return {
    // state
    status,
    connectedAt,
    lastError,
    identity,
    serverRooms,
    activeRoom,
    messages,
    onlineCounts,
    onlineUsers,
    notifications,
    typingUsers,
    unreadCount,
    // getters
    isConnected,
    currentMessages,
    currentOnline,
    currentTypingUsers,
    // actions
    connect,
    disconnect,
    switchRoom,
    sendMessage,
    sendTyping,
    loadHistory,
    clearRoom,
    markNotificationsRead,
    clearNotifications,
  }
})
