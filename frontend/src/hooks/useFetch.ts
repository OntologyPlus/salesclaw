import { useEffect, useRef, useState, useCallback } from 'react'

interface FetchResult<T> {
  data: T | null
  loading: boolean
  error: Error | null
  refetch: () => void
}

// 简单缓存：key 为 fetcher 字符串，5s 内复用
// 注意：key 基于 fetcher 源码 + deps 序列化——fetcher 闭包引用的外部变量必须完整列入 deps，
// 否则源码相同但闭包不同的组件实例会互相命中缓存（跨实例缓存污染）
const cache = new Map<string, { data: unknown; expireAt: number }>()
const CACHE_TTL = 5000
const CACHE_MAX_ENTRIES = 100

// 泛型数据获取 Hook，自动 loading / error 状态，5s 缓存
export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []): FetchResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<Error | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const [trigger, setTrigger] = useState(0)

  const refetch = useCallback(() => setTrigger((t) => t + 1), [])

  useEffect(() => {
    let cancelled = false
    const key = fetcherRef.current.toString() + JSON.stringify(deps)
    const cached = cache.get(key)
    if (cached && cached.expireAt > Date.now()) {
      setData(cached.data as T)
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError(null)
        cache.set(key, { data: result, expireAt: Date.now() + CACHE_TTL })
        // 防止长会话下缓存无限增长：超阈值时清理过期条目
        if (cache.size > CACHE_MAX_ENTRIES) {
          const now = Date.now()
          for (const [k, v] of cache) {
            if (v.expireAt <= now) cache.delete(k)
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err : new Error(String(err)))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger, ...deps])

  return { data, loading, error, refetch }
}

export default useFetch
