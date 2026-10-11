import { useMemo, useRef, useState, useEffect, type ReactNode, type UIEvent } from 'react'

interface VirtualListProps<T> {
  items: T[]
  itemHeight: number
  height: number
  overscan?: number
  getKey: (item: T, index: number) => string | number
  renderItem: (item: T, index: number) => ReactNode
  className?: string
}

/** 轻量定高虚拟列表（无第三方依赖），用于通知等中等长度列表 */
export default function VirtualList<T>({
  items,
  itemHeight,
  height,
  overscan = 6,
  getKey,
  renderItem,
  className = '',
}: VirtualListProps<T>) {
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)

  useEffect(() => {
    setScrollTop(0)
    if (scrollerRef.current) scrollerRef.current.scrollTop = 0
  }, [items.length])

  const { start, end, offsetY, totalHeight } = useMemo(() => {
    const totalHeight = items.length * itemHeight
    const visible = Math.ceil(height / itemHeight)
    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan)
    const end = Math.min(items.length, start + visible + overscan * 2)
    return { start, end, offsetY: start * itemHeight, totalHeight }
  }, [items.length, itemHeight, height, overscan, scrollTop])

  const onScroll = (e: UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop)
  }

  const slice = items.slice(start, end)

  return (
    <div
      ref={scrollerRef}
      className={`overflow-y-auto ${className}`}
      style={{ height }}
      onScroll={onScroll}
      role="list"
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {slice.map((item, i) => {
            const index = start + i
            return (
              <div key={getKey(item, index)} style={{ height: itemHeight }} role="listitem">
                {renderItem(item, index)}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
