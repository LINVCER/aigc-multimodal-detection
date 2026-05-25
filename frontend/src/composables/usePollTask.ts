/**
 * 任务轮询 Composable
 * 用于检测任务的状态轮询
 */

import { ref, onUnmounted } from 'vue'
import api from '@/api'

export interface PollTaskOptions {
  /** 最大重试次数 */
  maxRetries?: number
  /** 轮询间隔（毫秒） */
  interval?: number
  /** 任务状态接口路径 */
  statusEndpoint?: string
  /** 任务结果接口路径 */
  resultEndpoint?: string
}

export interface PollTaskResult<T = unknown> {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  result?: T
  error?: string
}

export function usePollTask<T = unknown>(options: PollTaskOptions = {}) {
  const {
    maxRetries = 60,
    interval = 2000,
    statusEndpoint = '/detect/status',
    resultEndpoint = '/detect/result',
  } = options

  const isPolling = ref(false)
  const progress = ref(0)
  const error = ref<string | null>(null)
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0

  /**
   * 停止轮询
   */
  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    isPolling.value = false
  }

  /**
   * 轮询任务状态
   * @param taskId 任务ID
   * @param onResult 结果回调
   * @param onFailed 失败回调
   */
  async function pollTask(
    taskId: string,
    onResult: (result: T) => void,
    onFailed?: (error: string) => void
  ) {
    isPolling.value = true
    error.value = null
    retryCount = 0

    const checkStatus = async () => {
      try {
        retryCount++
        progress.value = Math.min(95, Math.round((retryCount / maxRetries) * 100))

        // 检查任务状态
        const statusRes = await api.get(`${statusEndpoint}/${taskId}`)
        const statusData = statusRes.data as PollTaskResult<T>

        if (statusData.status === 'completed') {
          // 任务完成，获取结果
          const resultRes = await api.get(`${resultEndpoint}/${taskId}`)
          progress.value = 100
          onResult(resultRes.data as T)
          stopPolling()
          return
        }

        if (statusData.status === 'failed') {
          // 任务失败
          const errorMsg = statusData.error || '检测失败'
          error.value = errorMsg
          onFailed?.(errorMsg)
          stopPolling()
          return
        }

        // 继续轮询
        if (retryCount < maxRetries) {
          pollTimer = setTimeout(checkStatus, interval)
        } else {
          // 超时
          const errorMsg = '检测超时，请重试'
          error.value = errorMsg
          onFailed?.(errorMsg)
          stopPolling()
        }
      } catch (e: unknown) {
        const errorMsg = e instanceof Error ? e.message : '网络错误'
        error.value = errorMsg
        onFailed?.(errorMsg)
        stopPolling()
      }
    }

    // 开始轮询
    pollTimer = setTimeout(checkStatus, interval)
  }

  // 组件卸载时停止轮询
  onUnmounted(() => {
    stopPolling()
  })

  return {
    isPolling,
    progress,
    error,
    pollTask,
    stopPolling,
  }
}
