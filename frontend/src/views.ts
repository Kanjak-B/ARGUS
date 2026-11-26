import type { NodeStatus, Topology } from './api'
import { STATUS } from './status'

export type View = 'all' | 'online'

export const VIEWS: Record<View, { label: string; fileSuffix: string; statuses: NodeStatus[] }> = {
  all: {
    label: 'Full view',
    fileSuffix: 'full',
    statuses: Object.keys(STATUS) as NodeStatus[],
  },
  online: { label: 'Online', fileSuffix: 'online', statuses: ['ok'] },
}

/** Même règle que « online_only » côté serveur, qui produit les exports JSON et Excel. */
export function applyView(topology: Topology, view: View): Topology {
  if (view === 'all') return topology
  const nodes = topology.nodes.filter((node) => node.status === 'ok')
  const ids = new Set(nodes.map((node) => node.id))
  const edges = topology.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target))
  return { ...topology, nodes, edges }
}
