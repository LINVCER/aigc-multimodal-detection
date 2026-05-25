/**
 * 从 Axios 错误中提取用户友好的错误信息
 */
export function extractApiErrorMessage(e: any, fallback = "操作失败"): string {
  if (e?.response?.data?.detail) {
    const detail = e.response.data.detail
    if (Array.isArray(detail)) {
      return detail.map((d: any) => d.msg || String(d)).join("; ")
    }
    return String(detail)
  }
  if (e?.code === "ECONNABORTED") return "请求超时，请重试"
  if (!e?.response) return "网络连接失败，请检查网络"
  return `${fallback} (${e.response?.status || "未知错误"})`
}
