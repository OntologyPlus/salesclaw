import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Network, Search, Box, Link2, Database, Activity, Layers, X, GitBranch, ArrowRight } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import { ontologyApi } from '@/services/ontology'

// ──────────────────────────────────────────────
// 类型定义
// ──────────────────────────────────────────────

interface OntologyObject {
  name: string
  display_name: string
  domain: string
  description?: string
  fields?: string[]
  actions?: string[]
}

interface OntologyLink {
  name: string
  display_name: string
  source_object: string
  target_object: string
  cardinality: string
  description?: string
}

interface DomainStat {
  domain: string
  objects: number
  links: number
  actions: number
}

interface Stats {
  total_objects: number
  total_links: number
  total_actions: number
  domains: number
  domain_list?: string[]
}

// 域颜色映射
const DOMAIN_COLORS: Record<string, string> = {
  sales: '#3b82f6',       // blue
  training: '#10b981',    // emerald
  decision: '#f59e0b',    // amber
  collab: '#8b5cf6',      // violet
  knowledge: '#ec4899',   // pink
  common: '#64748b',      // slate
  unknown: '#94a3b8',     // slate-400
}

const DOMAIN_LABELS: Record<string, string> = {
  sales: '销售执行',
  training: '智能培训',
  decision: '决策支持',
  collab: '协同办公',
  knowledge: '知识库',
  common: '通用',
  unknown: '其他',
}

// ──────────────────────────────────────────────
// SVG 力导向图（简易版）
// ──────────────────────────────────────────────

interface GraphNode {
  id: string
  label: string
  domain: string
  x: number
  y: number
  vx: number
  vy: number
  degree: number
}

interface GraphEdge {
  source: string
  target: string
  label: string
}

function ForceGraph({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedNode: string | null
  onSelectNode: (id: string) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const animRef = useRef<number | null>(null)
  const nodesRef = useRef<GraphNode[]>(nodes)
  const edgesRef = useRef<GraphEdge[]>(edges)
  const [, forceRender] = useState(0)
  const frameCount = useRef(0)

  // 更新 refs
  useEffect(() => {
    nodesRef.current = nodes
    edgesRef.current = edges
  }, [nodes, edges])

  // 力导向布局
  const simulate = useCallback(() => {
    const W = 800
    const H = 600
    const CENTER_X = W / 2
    const CENTER_Y = H / 2
    const REPULSION = 1500
    const SPRING_LENGTH = 80
    const SPRING_K = 0.04
    const CENTER_K = 0.005
    const DAMPING = 0.85

    const ns = nodesRef.current
    const es = edgesRef.current

    if (ns.length === 0) return

    // 计算排斥力
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const dx = ns[i].x - ns[j].x
        const dy = ns[i].y - ns[j].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = REPULSION / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        ns[i].vx += fx
        ns[i].vy += fy
        ns[j].vx -= fx
        ns[j].vy -= fy
      }
    }

    // 计算弹簧力（边）
    const nodeMap = new Map(ns.map(n => [n.id, n]))
    for (const e of es) {
      const s = nodeMap.get(e.source)
      const t = nodeMap.get(e.target)
      if (!s || !t) continue
      const dx = t.x - s.x
      const dy = t.y - s.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = SPRING_K * (dist - SPRING_LENGTH)
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      s.vx += fx
      s.vy += fy
      t.vx -= fx
      t.vy -= fy
    }

    // 中心引力 + 更新位置
    for (const n of ns) {
      n.vx += (CENTER_X - n.x) * CENTER_K
      n.vy += (CENTER_Y - n.y) * CENTER_K
      n.vx *= DAMPING
      n.vy *= DAMPING
      n.x += n.vx
      n.y += n.vy
      // 边界约束
      n.x = Math.max(30, Math.min(W - 30, n.x))
      n.y = Math.max(30, Math.min(H - 30, n.y))
    }

    frameCount.current++
    forceRender(c => c + 1)

    // 最多 300 帧或收敛后停止
    if (frameCount.current < 300) {
      animRef.current = requestAnimationFrame(simulate)
    }
  }, [])

  // 初始化节点位置 + 启动模拟
  useEffect(() => {
    const ns = nodesRef.current
    // 初始化随机位置
    for (let i = 0; i < ns.length; i++) {
      if (ns[i].x === 0 && ns[i].y === 0) {
        const angle = (i / ns.length) * Math.PI * 2
        const radius = 200 + Math.random() * 50
        ns[i].x = 400 + Math.cos(angle) * radius
        ns[i].y = 300 + Math.sin(angle) * radius
      }
    }
    frameCount.current = 0
    animRef.current = requestAnimationFrame(simulate)
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [nodes, simulate])

  const currentNodes = nodesRef.current

  return (
    <svg ref={svgRef} viewBox="0 0 800 600" className="w-full h-full" style={{ minHeight: '400px' }}>
      {/* 边 */}
      {edges.map((e, i) => {
        const s = currentNodes.find(n => n.id === e.source)
        const t = currentNodes.find(n => n.id === e.target)
        if (!s || !t) return null
        return (
          <line
            key={i}
            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
            stroke="#cbd5e1"
            strokeWidth={1}
            opacity={0.5}
          />
        )
      })}
      {/* 节点 */}
      {currentNodes.map(n => {
        const color = DOMAIN_COLORS[n.domain] || DOMAIN_COLORS.unknown
        const r = 6 + Math.min(n.degree * 1.5, 12)
        const isSelected = n.id === selectedNode
        return (
          <g
            key={n.id}
            onClick={() => onSelectNode(n.id)}
            style={{ cursor: 'pointer' }}
          >
            <circle
              cx={n.x} cy={n.y} r={r}
              fill={color}
              opacity={isSelected ? 1 : 0.8}
              stroke={isSelected ? '#1e293b' : 'none'}
              strokeWidth={isSelected ? 2 : 0}
            />
            <text
              x={n.x} y={n.y - r - 4}
              textAnchor="middle"
              fontSize={9}
              fill="#475569"
              className="pointer-events-none"
            >
              {n.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ──────────────────────────────────────────────
// 主页面
// ──────────────────────────────────────────────

export default function OntologyPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [domains, setDomains] = useState<DomainStat[]>([])
  const [objects, setObjects] = useState<OntologyObject[]>([])
  const [links, setLinks] = useState<OntologyLink[]>([])
  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'graph' | 'objects' | 'links' | 'chain'>('graph')
  const [selectedObject, setSelectedObject] = useState<OntologyObject | null>(null)
  // L2 关系链推理状态
  const [chainRoot, setChainRoot] = useState<string>('')
  const [chainDepth, setChainDepth] = useState(2)
  const [chainSubgraph, setChainSubgraph] = useState<{ nodes: { name: string; display_name: string; domain: string }[]; edges: { source: string; target: string; source_display: string; target_display: string; link: string; display_name: string; relation: string; cardinality: string }[] } | null>(null)
  const [chainBusy, setChainBusy] = useState(false)
  const [chainError, setChainError] = useState<string | null>(null)
  const [objectRelations, setObjectRelations] = useState<{ outgoing: OntologyLink[]; incoming: OntologyLink[] } | null>(null)

  // 加载初始数据
  useEffect(() => {
    Promise.all([
      ontologyApi.getStats(),
      ontologyApi.getDomains(),
      ontologyApi.getObjects(),
      ontologyApi.getLinks(),
    ]).then(([s, d, objs, lnks]) => {
      setStats(s)
      setDomains(d.items || [])
      setObjects(objs.items || [])
      setLinks(lnks.items || [])
    }).catch(() => {
      // 静默失败
    })
  }, [])

  // 搜索
  useEffect(() => {
    if (!searchQuery.trim()) {
      ontologyApi.getObjects().then(r => setObjects(r.items || [])).catch(() => {})
      return
    }
    const timer = setTimeout(() => {
      ontologyApi.search(searchQuery).then(r => setObjects(r.items || [])).catch(() => {})
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // 筛选后的实体
  const filteredObjects = useMemo(() => {
    if (selectedDomains.size === 0) return objects
    return objects.filter(o => selectedDomains.has(o.domain))
  }, [objects, selectedDomains])

  // 图谱节点和边
  const { graphNodes, graphEdges } = useMemo(() => {
    const nodeMap = new Map<string, GraphNode>()
    const filteredNames = new Set(filteredObjects.map(o => o.name))

    // 计算度数
    const degreeMap = new Map<string, number>()
    for (const l of links) {
      if (filteredNames.has(l.source_object)) {
        degreeMap.set(l.source_object, (degreeMap.get(l.source_object) || 0) + 1)
      }
      if (filteredNames.has(l.target_object)) {
        degreeMap.set(l.target_object, (degreeMap.get(l.target_object) || 0) + 1)
      }
    }

    for (const o of filteredObjects) {
      nodeMap.set(o.name, {
        id: o.name,
        label: o.display_name || o.name,
        domain: o.domain,
        x: 0, y: 0, vx: 0, vy: 0,
        degree: degreeMap.get(o.name) || 0,
      })
    }

    const edges: GraphEdge[] = links
      .filter(l => filteredNames.has(l.source_object) && filteredNames.has(l.target_object))
      .map(l => ({ source: l.source_object, target: l.target_object, label: l.display_name }))

    return { graphNodes: Array.from(nodeMap.values()), graphEdges: edges }
  }, [filteredObjects, links])

  // 选择实体时加载详情
  const handleSelectNode = useCallback((id: string) => {
    const obj = objects.find(o => o.name === id)
    if (obj) {
      setSelectedObject(obj)
      ontologyApi.getRelations(id).then(r => {
        setObjectRelations({ outgoing: r.outgoing || [], incoming: r.incoming || [] })
      }).catch(() => {
        setObjectRelations(null)
      })
    }
  }, [objects])

  // 域切换
  const toggleDomain = (domain: string) => {
    setSelectedDomains(prev => {
      const next = new Set(prev)
      if (next.has(domain)) next.delete(domain)
      else next.add(domain)
      return next
    })
  }

  // 初次加载后默认根对象
  useEffect(() => {
    if (!chainRoot && objects.length) setChainRoot(objects[0].name)
  }, [objects, chainRoot])

  // L2 关系链推理：查询根对象的 N 跳邻居子图
  const runChainQuery = useCallback((rootOverride?: string) => {
    const root = rootOverride ?? chainRoot
    if (!root) return
    setChainBusy(true)
    setChainError(null)
    ontologyApi.getNeighbors(root, chainDepth)
      .then(r => setChainSubgraph(r?.subgraph || { nodes: [], edges: [] }))
      .catch(() => setChainError('关系链推理失败'))
      .finally(() => setChainBusy(false))
  }, [chainRoot, chainDepth])

  // chainRoot 就绪后自动发起首次推理（避免点击时的状态闭包竞态）
  useEffect(() => {
    if (chainRoot) runChainQuery(chainRoot)
  }, [chainRoot, runChainQuery])

  // 关系链子图 → ForceGraph 节点/边
  const { chainGraphNodes, chainGraphEdges } = useMemo(() => {
    if (!chainSubgraph) return { chainGraphNodes: [] as GraphNode[], chainGraphEdges: [] as GraphEdge[] }
    const degreeMap = new Map<string, number>()
    for (const e of chainSubgraph.edges) {
      degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1)
      degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1)
    }
    const nodes: GraphNode[] = chainSubgraph.nodes.map((o, i) => ({
      id: o.name,
      label: o.display_name || o.name,
      domain: o.domain,
      x: 0, y: 0, vx: 0, vy: 0,
      degree: degreeMap.get(o.name) || 0,
    }))
    const edges: GraphEdge[] = chainSubgraph.edges
      .filter(e => chainSubgraph.nodes.some(n => n.name === e.source) && chainSubgraph.nodes.some(n => n.name === e.target))
      .map(e => ({ source: e.source, target: e.target, label: e.display_name }))
    return { chainGraphNodes: nodes, chainGraphEdges: edges }
  }, [chainSubgraph])

  return (
    <div>
      <PageHeader
        title="本体图谱"
        description="Ontology 注册表 · 实体 · 关系 · Action 可视化"
        breadcrumbs={[{ label: '系统管理' }, { label: '本体图谱' }]}
        icon={<Network className="w-5 h-5" />}
        gradient
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <StatCard icon={<Box className="w-4 h-4" />} label="实体" value={stats?.total_objects ?? 0} color="blue" />
        <StatCard icon={<Link2 className="w-4 h-4" />} label="关系" value={stats?.total_links ?? 0} color="violet" />
        <StatCard icon={<Activity className="w-4 h-4" />} label="Action" value={stats?.total_actions ?? 0} color="amber" />
        <StatCard icon={<Layers className="w-4 h-4" />} label="域" value={stats?.domains ?? 0} color="emerald" />
      </div>

      <div className="flex gap-4">
        {/* 左侧筛选 */}
        <div className="w-56 shrink-0 space-y-3">
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-medium text-slate-600 dark:text-slate-300">
              <Search className="w-3.5 h-3.5" />
              搜索实体
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="名称或显示名..."
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-medium text-slate-600 dark:text-slate-300">
              <Layers className="w-3.5 h-3.5" />
              域过滤
            </div>
            <div className="space-y-1.5">
              {domains.map(d => (
                <label key={d.domain} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={selectedDomains.has(d.domain)}
                    onChange={() => toggleDomain(d.domain)}
                    className="rounded border-slate-300"
                  />
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: DOMAIN_COLORS[d.domain] || DOMAIN_COLORS.unknown }}
                  />
                  <span className="text-slate-700 dark:text-slate-300">
                    {DOMAIN_LABELS[d.domain] || d.domain}
                  </span>
                  <span className="ml-auto text-xs text-slate-400">{d.objects}</span>
                </label>
              ))}
            </div>
            {selectedDomains.size > 0 && (
              <button
                onClick={() => setSelectedDomains(new Set())}
                className="mt-2 text-xs text-brand-600 hover:underline"
              >
                清除筛选
              </button>
            )}
          </div>
        </div>

        {/* 右侧主区域 */}
        <div className="flex-1 min-w-0">
          {/* Tab 切换 */}
          <div className="flex items-center gap-1 mb-3 border-b border-slate-200 dark:border-slate-700">
            <TabButton active={activeTab === 'graph'} onClick={() => setActiveTab('graph')} icon={<Network className="w-4 h-4" />}>
              图谱视图
            </TabButton>
            <TabButton active={activeTab === 'objects'} onClick={() => setActiveTab('objects')} icon={<Box className="w-4 h-4" />}>
              实体列表 ({filteredObjects.length})
            </TabButton>
            <TabButton active={activeTab === 'links'} onClick={() => setActiveTab('links')} icon={<Link2 className="w-4 h-4" />}>
              关系列表 ({links.length})
            </TabButton>
            <TabButton active={activeTab === 'chain'} onClick={() => setActiveTab('chain')} icon={<GitBranch className="w-4 h-4" />}>
              关系链推理 (L2)
            </TabButton>
          </div>

          {/* 图谱视图 */}
          {activeTab === 'graph' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="lg:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700 text-xs text-slate-500">
                  节点 {graphNodes.length} · 边 {graphEdges.length}
                  {graphNodes.length > 80 && <span className="ml-2 text-amber-500">（节点较多，仅展示部分）</span>}
                </div>
                <div className="h-[500px]">
                  {graphNodes.length > 0 ? (
                    <ForceGraph
                      nodes={graphNodes.slice(0, 80)}
                      edges={graphEdges.filter(e => graphNodes.slice(0, 80).some(n => n.id === e.source) && graphNodes.slice(0, 80).some(n => n.id === e.target))}
                      selectedNode={selectedObject?.name || null}
                      onSelectNode={handleSelectNode}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                      <Database className="w-8 h-8 mb-2 mr-2" />
                      暂无数据
                    </div>
                  )}
                </div>
              </div>

              {/* 详情面板 */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
                {selectedObject ? (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {selectedObject.display_name}
                      </h3>
                      <button onClick={() => { setSelectedObject(null); setObjectRelations(null) }} className="text-slate-400 hover:text-slate-600">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div>
                        <span className="text-slate-500">name: </span>
                        <code className="text-slate-800 dark:text-slate-200">{selectedObject.name}</code>
                      </div>
                      <div>
                        <span className="text-slate-500">域: </span>
                        <span
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]"
                          style={{ backgroundColor: (DOMAIN_COLORS[selectedObject.domain] || DOMAIN_COLORS.unknown) + '20', color: DOMAIN_COLORS[selectedObject.domain] || DOMAIN_COLORS.unknown }}
                        >
                          {DOMAIN_LABELS[selectedObject.domain] || selectedObject.domain}
                        </span>
                      </div>
                      {selectedObject.description && (
                        <div>
                          <span className="text-slate-500">描述: </span>
                          <span className="text-slate-700 dark:text-slate-300">{selectedObject.description}</span>
                        </div>
                      )}
                      {selectedObject.fields && selectedObject.fields.length > 0 && (
                        <div>
                          <div className="text-slate-500 mb-1">字段 ({selectedObject.fields.length}):</div>
                          <div className="flex flex-wrap gap-1">
                            {selectedObject.fields.map(f => (
                              <code key={f} className="px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-[10px] text-slate-600 dark:text-slate-300">
                                {f}
                              </code>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedObject.actions && selectedObject.actions.length > 0 && (
                        <div>
                          <div className="text-slate-500 mb-1">Actions ({selectedObject.actions.length}):</div>
                          <div className="flex flex-wrap gap-1">
                            {selectedObject.actions.map(a => (
                              <code key={a} className="px-1 py-0.5 rounded bg-amber-50 dark:bg-amber-900/20 text-[10px] text-amber-700 dark:text-amber-300">
                                {a}
                              </code>
                            ))}
                          </div>
                        </div>
                      )}
                      {objectRelations && (
                        <div>
                          <div className="text-slate-500 mb-1">
                            关系（出向 {objectRelations.outgoing.length} + 入向 {objectRelations.incoming.length}）
                          </div>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {[...objectRelations.outgoing, ...objectRelations.incoming].map((r, i) => (
                              <div key={i} className="text-[10px] text-slate-600 dark:text-slate-400">
                                <span className="text-slate-400">{r.source_object}</span>
                                <span className="mx-1 text-slate-400">→</span>
                                <span className="text-slate-400">{r.target_object}</span>
                                <span className="ml-1 text-slate-500">({r.cardinality})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 text-xs py-8">
                    <Network className="w-8 h-8 mb-2" />
                    <p>点击图谱中的节点查看详情</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 实体列表 */}
          {activeTab === 'objects' && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-700/50 text-xs text-slate-500">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">名称</th>
                      <th className="text-left px-4 py-2 font-medium">显示名</th>
                      <th className="text-left px-4 py-2 font-medium">域</th>
                      <th className="text-left px-4 py-2 font-medium">字段数</th>
                      <th className="text-left px-4 py-2 font-medium">Actions</th>
                      <th className="text-left px-4 py-2 font-medium">描述</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredObjects.map(o => (
                      <tr
                        key={o.name}
                        onClick={() => handleSelectNode(o.name)}
                        className="border-t border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30 cursor-pointer"
                      >
                        <td className="px-4 py-2"><code className="text-xs text-brand-600">{o.name}</code></td>
                        <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{o.display_name}</td>
                        <td className="px-4 py-2">
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]"
                            style={{ backgroundColor: (DOMAIN_COLORS[o.domain] || DOMAIN_COLORS.unknown) + '20', color: DOMAIN_COLORS[o.domain] || DOMAIN_COLORS.unknown }}>
                            {DOMAIN_LABELS[o.domain] || o.domain}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-500">{o.fields?.length ?? 0}</td>
                        <td className="px-4 py-2 text-slate-500">{o.actions?.length ?? 0}</td>
                        <td className="px-4 py-2 text-xs text-slate-500 max-w-xs truncate">{o.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 关系列表 */}
          {activeTab === 'links' && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-700/50 text-xs text-slate-500">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">关系名</th>
                      <th className="text-left px-4 py-2 font-medium">显示名</th>
                      <th className="text-left px-4 py-2 font-medium">源实体</th>
                      <th className="text-left px-4 py-2 font-medium">目标实体</th>
                      <th className="text-left px-4 py-2 font-medium">基数</th>
                      <th className="text-left px-4 py-2 font-medium">描述</th>
                    </tr>
                  </thead>
                  <tbody>
                    {links.map(l => (
                      <tr key={l.name} className="border-t border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30">
                        <td className="px-4 py-2"><code className="text-xs text-violet-600">{l.name}</code></td>
                        <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{l.display_name}</td>
                        <td className="px-4 py-2"><code className="text-xs text-brand-600">{l.source_object}</code></td>
                        <td className="px-4 py-2"><code className="text-xs text-brand-600">{l.target_object}</code></td>
                        <td className="px-4 py-2"><span className="text-xs text-slate-500">{l.cardinality}</span></td>
                        <td className="px-4 py-2 text-xs text-slate-500 max-w-xs truncate">{l.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 关系链推理 (L2 跨对象归因) */}
          {activeTab === 'chain' && (
            <div className="space-y-3">
              {/* 控制条 */}
              <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-indigo-500/30 bg-indigo-500/5 dark:border-indigo-500/40 dark:bg-indigo-500/10 p-3">
                <div className="flex-1 min-w-[200px]">
                  <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">根对象</label>
                  <select
                    value={chainRoot}
                    onChange={e => setChainRoot(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  >
                    {objects.map(o => (
                      <option key={o.name} value={o.name}>{o.display_name}（{o.name}）</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">跳数 N</label>
                  <select
                    value={chainDepth}
                    onChange={e => setChainDepth(Number(e.target.value))}
                    className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  >
                    {[1, 2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n} 跳</option>)}
                  </select>
                </div>
                <button
                  onClick={() => runChainQuery()}
                  disabled={chainBusy || !chainRoot}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
                >
                  <GitBranch className="w-4 h-4" /> {chainBusy ? '推理中…' : '开始推理'}
                </button>
              </div>

              {chainError && (
                <div className="rounded-lg border border-rose-300 bg-rose-50 dark:bg-rose-950/30 px-3 py-2 text-sm text-rose-600 dark:text-rose-300">
                  {chainError}
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                {/* 关系链子图 */}
                <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                  <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700 text-xs text-slate-500 flex items-center justify-between">
                    <span>N 跳关系链子图（确定性规则 · 跨对象传导）</span>
                    <span>{chainGraphNodes.length} 节点 · {chainGraphEdges.length} 边</span>
                  </div>
                  <div className="h-[460px]">
                    {chainGraphNodes.length > 0 ? (
                      <ForceGraph
                        nodes={chainGraphNodes}
                        edges={chainGraphEdges}
                        selectedNode={null}
                        onSelectNode={(id) => { setChainRoot(id); runChainQuery(id) }}
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                        <GitBranch className="w-8 h-8 mb-2 mr-2" />
                        暂无关系链数据
                      </div>
                    )}
                  </div>
                </div>

                {/* 邻居列表 */}
                <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
                  <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    <ArrowRight className="w-4 h-4 text-indigo-500" /> N 跳邻居
                  </h3>
                  {chainSubgraph && chainSubgraph.nodes.length > 0 ? (
                    <div className="max-h-[400px] space-y-1.5 overflow-auto pr-1">
                      {chainSubgraph.nodes.map(n => (
                        <button
                          key={n.name}
                          onClick={() => { setChainRoot(n.name); runChainQuery(n.name) }}
                          className="flex w-full items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 px-2.5 py-1.5 text-left transition hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40"
                        >
                          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: DOMAIN_COLORS[n.domain] || DOMAIN_COLORS.unknown }} />
                          <span className="flex-1 text-sm text-slate-700 dark:text-slate-200">{n.display_name}</span>
                          <span className="text-[10px] text-slate-400">{n.name}</span>
                          {n.name === chainRoot && <span className="rounded-full bg-indigo-600/20 px-1.5 py-0.5 text-[10px] text-indigo-400">根</span>}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">无邻居数据</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────
// 子组件
// ──────────────────────────────────────────────

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300',
    violet: 'bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300',
    amber: 'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-300',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300',
  }
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <div className="flex items-center gap-2 mb-1">
        <div className={`flex items-center justify-center w-7 h-7 rounded-lg ${colorMap[color] || colorMap.blue}`}>
          {icon}
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</div>
    </div>
  )
}

function TabButton({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-brand-600 text-brand-600 dark:text-brand-400'
          : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
      }`}
    >
      {icon}
      {children}
    </button>
  )
}
