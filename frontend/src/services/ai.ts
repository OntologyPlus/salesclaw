import api from './api'
import type { ApiResponse, Agent, Action, ChatSendResponse } from '@/types'

// 发送聊天消息
export async function chatSend(
  message: string,
  agent?: string,
  session_id?: string
): Promise<ChatSendResponse> {
  const res = await api.post<ApiResponse<ChatSendResponse>>('/ai/chat/send', {
    message,
    agent,
    session_id,
    stream: false,
  })
  return res.data.data
}

// 终止对话
export async function chatAbort(session_id: string): Promise<void> {
  await api.post<ApiResponse<null>>(`/ai/chat/${session_id}/abort`)
}

// 列出所有 Agent
export async function listAgents(): Promise<Agent[]> {
  const res = await api.get<ApiResponse<Agent[]>>('/agents')
  return res.data.data
}

// 列出所有 Action
export async function listActions(): Promise<Action[]> {
  const res = await api.get<ApiResponse<Action[]>>('/actions')
  return res.data.data
}
