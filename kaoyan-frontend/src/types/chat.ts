/** AI 对话模块类型定义，对应后端 /api/ai/* */

/** 消息角色：用户 / AI 助手 */
export type ChatRole = 'user' | 'assistant'

/** 会话（GET /ai/sessions 列表元素、POST /ai/sessions 响应） */
export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

/** 会话内的一条消息 */
export interface ChatMessage {
  id: number
  role: ChatRole
  content: string
  created_at: string
}

/** POST /ai/sessions 请求体 */
export interface CreateSessionPayload {
  title?: string
}

/** POST /ai/sessions/{id}/messages 请求体 */
export interface SendMessagePayload {
  content: string
}

/** POST /ai/sessions/{id}/messages 响应：同时返回用户消息与 AI 回复 */
export interface SendMessageResponse {
  user_message: ChatMessage
  assistant_message: ChatMessage
}
