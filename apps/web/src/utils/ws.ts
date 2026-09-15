/**
 * 可重连的 WebSocket 客户端。
 *
 * 特性:
 *  - 连接地址: `${VITE_WS_BASE_URL}?token=<access_token>&room=<room>` (token 每次重连前实时读取)
 *  - 心跳: 每 20s 发送 {"type":"ping"}
 *  - 断线重连: 指数退避 + 抖动, 上限 30s
 *  - 离线队列: 未连接时发出的消息先入队, 连接成功后按序补发
 *  - 事件: message | open | close | error | heartbeat, 支持 on/off
 *  - close(): 主动关闭并停止重连
 */

import type { ClientMessage, ServerMessage, WsStatus } from '@/types/ws'

/** 心跳间隔 (毫秒) */
const HEARTBEAT_INTERVAL = 20_000
/** 重连退避上限 (毫秒) */
const MAX_BACKOFF = 30_000
/** 退避基数 (毫秒) */
const BASE_BACKOFF = 1_000
/** 离线队列上限 */
const MAX_QUEUE = 100

/** 事件负载 */
export interface WsEventMap {
  open: void
  close: { code: number; reason: string; willReconnect: boolean }
  error: Event
  message: ServerMessage
  heartbeat: { ts: number }
}

export type WsEventName = keyof WsEventMap

export type WsHandler<K extends WsEventName> = (payload: WsEventMap[K]) => void

/** 底层 socket 抽象, 便于单测注入 fake */
export type SocketFactory = (url: string) => WebSocket

export interface WsClientOptions {
  /** 生成连接地址 (每次重连都会重新调用, 以便携带最新 token) */
  urlFactory: () => string
  /** socket 构造器, 默认 window.WebSocket */
  socketFactory?: SocketFactory
  /** 心跳间隔, 默认 20s */
  heartbeatInterval?: number
  /** 退避上限, 默认 30s */
  maxBackoff?: number
}

export class WsClient {
  private socket: WebSocket | null = null
  private status: WsStatus = 'idle'
  /** 是否被主动关闭 (关闭后不再自动重连) */
  private manualClose = false
  private attempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private readonly queue: string[] = []
  private readonly handlers: { [K in WsEventName]: Set<WsHandler<K>> } = {
    open: new Set(),
    close: new Set(),
    error: new Set(),
    message: new Set(),
    heartbeat: new Set(),
  }

  private readonly urlFactory: () => string
  private readonly socketFactory: SocketFactory
  private readonly heartbeatInterval: number
  private readonly maxBackoff: number

  constructor(options: WsClientOptions) {
    this.urlFactory = options.urlFactory
    this.socketFactory =
      options.socketFactory ?? ((url: string) => new WebSocket(url) as WebSocket)
    this.heartbeatInterval = options.heartbeatInterval ?? HEARTBEAT_INTERVAL
    this.maxBackoff = options.maxBackoff ?? MAX_BACKOFF
  }

  /** 当前连接状态 */
  getStatus(): WsStatus {
    return this.status
  }

  /** 是否已连接 */
  isOpen(): boolean {
    return this.status === 'open'
  }

  /** 待发送队列长度 */
  getQueueSize(): number {
    return this.queue.length
  }

  /** 注册事件监听 */
  on<K extends WsEventName>(event: K, handler: WsHandler<K>): void {
    this.handlers[event].add(handler as never)
  }

  /** 注销事件监听 */
  off<K extends WsEventName>(event: K, handler: WsHandler<K>): void {
    this.handlers[event].delete(handler as never)
  }

  /** 建立连接 (已连接时为空操作; 若处于关闭状态会重置退避) */
  connect(): void {
    if (this.status === 'open' || this.status === 'connecting') return
    this.manualClose = false
    this.clearReconnectTimer()
    this.openSocket()
  }

  /** 主动关闭并停止重连 */
  close(code = 1000, reason = 'client close'): void {
    this.manualClose = true
    this.clearReconnectTimer()
    this.clearHeartbeat()
    const socket = this.socket
    this.socket = null
    if (socket && (socket.readyState === 0 || socket.readyState === 1)) {
      this.status = 'closing'
      try {
        socket.close(code, reason)
      } catch {
        // 忽略关闭异常 (jsdom / 已断开)
      }
    }
    this.status = 'closed'
  }

  /** 发送消息: 未连接时入队, 连接后自动补发 */
  send(message: ClientMessage): boolean {
    const raw = JSON.stringify(message)
    if (this.isOpen() && this.socket) {
      try {
        this.socket.send(raw)
        return true
      } catch {
        this.enqueue(raw)
        return false
      }
    }
    this.enqueue(raw)
    return false
  }

  /** 便捷方法: 切换聊天室 */
  joinRoom(room: string): boolean {
    return this.send({ type: 'join', room })
  }

  /** 便捷方法: 发送文本消息 */
  sendChat(room: string, content: string): boolean {
    return this.send({ type: 'chat', room, content })
  }

  /** 便捷方法: 发送正在输入 */
  sendTyping(room: string): boolean {
    return this.send({ type: 'typing', room })
  }

  /* ------------------------------ 内部实现 ------------------------------ */

  private enqueue(raw: string): void {
    if (this.queue.length >= MAX_QUEUE) this.queue.shift()
    this.queue.push(raw)
  }

  private flushQueue(): void {
    if (!this.socket || this.queue.length === 0) return
    const pending = [...this.queue]
    this.queue.length = 0
    for (const raw of pending) {
      try {
        this.socket.send(raw)
      } catch {
        this.enqueue(raw)
      }
    }
  }

  private openSocket(): void {
    this.status = 'connecting'
    let socket: WebSocket
    try {
      socket = this.socketFactory(this.urlFactory())
    } catch (error) {
      this.status = 'closed'
      this.emit('error', error as Event)
      this.scheduleReconnect()
      return
    }

    this.socket = socket

    socket.onopen = () => {
      this.status = 'open'
      this.attempts = 0
      this.startHeartbeat()
      this.emit('open', undefined)
      this.flushQueue()
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      let parsed: ServerMessage
      try {
        parsed = JSON.parse(event.data) as ServerMessage
      } catch {
        return
      }
      if (parsed.type === 'pong') {
        this.emit('heartbeat', { ts: parsed.ts ?? Date.now() })
      }
      this.emit('message', parsed)
    }

    socket.onerror = (event: Event) => {
      this.emit('error', event)
    }

    socket.onclose = (event: CloseEvent) => {
      this.clearHeartbeat()
      this.socket = null
      this.status = 'closed'
      const willReconnect = !this.manualClose
      this.emit('close', {
        code: event?.code ?? 1006,
        reason: event?.reason ?? '',
        willReconnect,
      })
      if (willReconnect) this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    if (this.manualClose || this.reconnectTimer) return
    this.status = 'reconnecting'
    const backoff = Math.min(BASE_BACKOFF * 2 ** this.attempts, this.maxBackoff)
    // 抖动: ±30%, 避免多客户端同时重连
    const jitter = backoff * 0.3 * (Math.random() * 2 - 1)
    const delay = Math.max(BASE_BACKOFF / 2, Math.round(backoff + jitter))
    this.attempts += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.manualClose) return
      this.openSocket()
    }, delay)
  }

  private startHeartbeat(): void {
    this.clearHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (!this.isOpen()) return
      this.send({ type: 'ping' })
    }, this.heartbeatInterval)
  }

  private clearHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private emit<K extends WsEventName>(event: K, payload: WsEventMap[K]): void {
    for (const handler of this.handlers[event] as Set<WsHandler<K>>) {
      try {
        handler(payload)
      } catch (error) {
        // 单个监听器异常不应影响其他监听器
        console.error('[ws] handler error', error)
      }
    }
  }
}

/** 把 `/ws` 之类的相对路径解析为绝对 ws(s):// 地址 */
export function resolveWsUrl(
  base: string | undefined,
  token: string | null,
  room = 'lobby',
  locationHref?: string,
): string {
  const rawBase = (base && base.trim()) || '/ws'
  let url: URL

  if (/^wss?:\/\//i.test(rawBase)) {
    url = new URL(rawBase)
  } else {
    const href =
      locationHref ?? (typeof window !== 'undefined' ? window.location.href : 'http://localhost/')
    const origin = new URL(href)
    url = new URL(rawBase, origin.origin)
  }

  url.searchParams.set('room', room)
  if (token) url.searchParams.set('token', token)
  return url.toString()
}
