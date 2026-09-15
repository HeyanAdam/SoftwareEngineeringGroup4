/** WebSocket 消息协议类型 (前后端共享契约, 见 apps/api/app/schemas/ws.py) */

import type { ChatMessage } from './chat'

/** 客户端 -> 服务端 */
export interface ClientMessageMap {
  ping: { type: 'ping' }
  join: { type: 'join'; room: string }
  leave: { type: 'leave'; room: string }
  chat: { type: 'chat'; room: string; content: string }
  typing: { type: 'typing'; room: string }
}

export type ClientMessageType = keyof ClientMessageMap
export type ClientMessage = ClientMessageMap[ClientMessageType]

/** WebSocket 中的用户摘要 (welcome 消息) */
export interface WsUserSummary {
  id: number
  username: string
  is_superuser: boolean
}

/** 服务端 -> 客户端 (联合类型, 用 type 判别) */
export type ServerMessage =
  | { type: 'pong'; ts?: number }
  | { type: 'welcome'; ts?: number; user: WsUserSummary; rooms: string[] }
  | { type: 'joined'; room: string; ts?: number }
  | { type: 'left'; room: string; ts?: number }
  | { type: 'chat'; room: string; message: ChatMessage }
  | { type: 'presence'; room: string; online: number; users: string[] }
  | { type: 'notification'; level: 'info' | 'success' | 'warning' | 'error'; title: string; content: string; room?: string }
  | { type: 'error'; content: string }

/** WebSocket 连接状态 */
export type WsStatus = 'idle' | 'connecting' | 'open' | 'closing' | 'closed' | 'reconnecting'
