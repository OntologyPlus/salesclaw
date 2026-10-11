import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import VirtualList from './VirtualList'

describe('VirtualList', () => {
  it('renders a window of items', () => {
    const items = Array.from({ length: 100 }, (_, i) => ({ id: i, label: `Item ${i}` }))
    render(
      <VirtualList
        items={items}
        itemHeight={40}
        height={200}
        getKey={(item) => item.id}
        renderItem={(item) => <div>{item.label}</div>}
      />,
    )
    expect(screen.getByText('Item 0')).toBeInTheDocument()
    expect(screen.queryByText('Item 99')).not.toBeInTheDocument()
  })
})
