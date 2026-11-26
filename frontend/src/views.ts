import type { NodeStatus, Topology } from './api'
import { STATUS } from './status'

export type View = 'all' | 'online'

export const VIEWS: Record<View, { label: string; fileSuffix: string; statuses: NodeStatus[] }> = {
  all: {
    label: 'Vue complète',
    fileSuffix: 'complete',
    statuses: Object.keys(STATUS) as NodeStatus[],
  },
  online: { label: 'En ligne', fileSuffix: 'en_ligne', statuses: ['ok'] },
}

/** Même règle que « online_only » côté serveur, qui produit les exports JSON et Excel. */
export function applyView(topology: Topology, view: View): Topology {
  if (view === 'all') return topology
  const nodes = topology.nodes.filter((node) => node.status === 'ok')
  const ids = new Set(nodes.map((node) => node.id))
  const edges = topology.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target))
  return { ...topology, nodes, edges }
}
