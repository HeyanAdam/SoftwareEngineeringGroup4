/** AI 对话模块接口，对应后端 /api/ai/*（均需登录） */
import { request } from '@/utils/request'
import type { DeleteResult } from '@/types/api'
import type {
  ChatMessage,
  ChatSession,
  CreateSessionPayload,
  SendMessagePayload,
  SendMessageResponse,
} from '@/types/chat'

/** 会话列表 */
export function listSessions(): Promise<ChatSession[]> {
  return request.get<ChatSession[]>('/ai/sessions')
}

/** 新建会话 */
export function createSession(payload: CreateSessionPayload = {}): Promise<ChatSession> {
  return request.post<ChatSession>('/ai/sessions', payload)
}

/** 删除会话 */
export function deleteSession(sessionId: number): Promise<DeleteResult> {
  return request.delete<DeleteResult>(`/ai/sessions/${sessionId}`)
}

/** 某个会话的历史消息 */
export function listMessages(sessionId: number): Promise<ChatMessage[]> {
  return request.get<ChatMessage[]>(`/ai/sessions/${sessionId}/messages`)
}

/** 发送消息，后端同步返回用户消息与 AI 回复 */
export function sendMessage(
  sessionId: number,
  payload: SendMessagePayload,
): Promise<SendMessageResponse> {
  return request.post<SendMessageResponse>(`/ai/sessions/${sessionId}/messages`, payload)
}
