/** 聊天与通知类型 (对齐 apps/api/app/schemas/ws.py) */

/** 通知级别 */
export type NotificationLevel = 'info' | 'success' | 'warning' | 'error'

/** 聊天室 (GET /chat/rooms) */
export interface ChatRoom {
  id: number
  code: string
  name: string
  description: string | null
  is_default: boolean
}

/** 聊天消息 */
export interface ChatMessage {
  id: number | null
  room: string
  sender_id: number | null
  sender_name: string
  kind: string
  content: string
  created_at: string
  source: string | null
}

/** 在线统计 (GET /chat/online) */
export interface ChatOnlineStats {
  connections: number
  rooms: Record<string, number>
}

/** 广播响应 (POST /chat/broadcast) */
export interface BroadcastResponse {
  delivered: number
}

/** 站内通知 (来自 WebSocket) */
export interface WsNotification {
  id: string
  level: NotificationLevel
  title: string
  content: string
  receivedAt: number
  /** 已读标记 */
  read: boolean
}
