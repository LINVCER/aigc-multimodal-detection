import { defineStore } from "pinia"
import { ref, watch } from "vue"
import { useAuthStore } from "./auth"

interface CachedResult {
  id: string
  type: "text" | "image" | "thesis" | "batch" | "audio" | "tampering"
  title: string
  timestamp: string
  data: any
}

function getUserKey(): string {
  const auth = useAuthStore()
  const userId = auth.user?.id || auth.user?.username || "anonymous"
  return `detection_cache_${userId}`
}

export const useResultsStore = defineStore("results", () => {
  const auth = useAuthStore()
  const cache = ref<CachedResult[]>(loadCache())

  // 监听用户变化，切换缓存
  watch(() => auth.user, (newUser, oldUser) => {
    if (newUser?.id !== oldUser?.id || newUser?.username !== oldUser?.username) {
      cache.value = loadCache()
    }
  }, { deep: true })

  function loadCache(): CachedResult[] {
    try {
      const key = getUserKey()
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  }

  function saveCache() {
    const key = getUserKey()
    localStorage.setItem(key, JSON.stringify(cache.value.slice(-20)))
  }

  function add(type: string, title: string, data: any) {
    const id = Date.now().toString(36)
    cache.value.push({
      id,
      type: type as any,
      title,
      timestamp: new Date().toLocaleTimeString(),
      data,
    })
    saveCache()
    return id
  }

  function remove(id: string) {
    cache.value = cache.value.filter(r => r.id !== id)
    saveCache()
  }

  function clear() {
    cache.value = []
    saveCache()
  }

  function getLatest(type?: string) {
    if (type) return cache.value.filter(r => r.type === type).slice(-3)
    return cache.value.slice(-5)
  }

  return { cache, add, remove, clear, getLatest }
})
