/** 聊天室 / 通知接口 (WebSocket 的 HTTP 补充) */

import { get, post } from '@/utils/request'
import type {
  BroadcastResponse,
  ChatMessage,
  ChatOnlineStats,
  ChatRoom,
  NotificationLevel,
} from '@/types/chat'

/** 聊天室列表 */
export function listRooms(): Promise<ChatRoom[]> {
  return get<ChatRoom[]>('/chat/rooms')
}

/** 历史消息 (before_id 为游标, 返回该 id 之前的消息) */
export function listMessages(
  roomCode: string,
  limit = 50,
  beforeId?: number,
): Promise<ChatMessage[]> {
  return get<ChatMessage[]>(`/chat/rooms/${roomCode}/messages`, { limit, before_id: beforeId })
}

/** 在线状态 (本实例视图) */
export function getOnlineStats(): Promise<ChatOnlineStats> {
  return get<ChatOnlineStats>('/chat/online')
}

/** 全站广播通知 */
export function broadcast(
  title: string,
  content = '',
  level: NotificationLevel = 'info',
): Promise<BroadcastResponse> {
  return post<BroadcastResponse>('/chat/broadcast', undefined, {
    params: { title, content, level },
  })
}
