import { describe, expect, it } from 'vitest'
import {
  allNavItems,
  getNavItemsByPrefixes,
  navGroups,
  sidebarNavGroups,
} from './navConfig'

describe('navConfig hub tiers', () => {
  it('marks every item with a tier', () => {
    for (const item of allNavItems) {
      expect(item.tier === 'primary' || item.tier === 'secondary').toBe(true)
    }
  })

  it('sidebar exposes full catalog with primary + secondary', () => {
    const flat = sidebarNavGroups.flatMap((g) => g.items)
    expect(flat.length).toBe(allNavItems.length)
    expect(flat.some((i) => i.tier === 'secondary')).toBe(true)
    expect(flat.some((i) => (i.tier ?? 'primary') === 'primary')).toBe(true)
  })

  it('keeps secondary routes discoverable via prefix helper', () => {
    const sales = getNavItemsByPrefixes(['/sales'], { excludeExact: ['/sales'] })
    expect(sales.some((i) => i.path === '/sales/roi')).toBe(true)
    expect(sales.some((i) => i.path === '/sales')).toBe(false)
  })

  it('retains compliance group in full nav', () => {
    expect(navGroups.some((g) => g.id === 'compliance')).toBe(true)
  })
})
