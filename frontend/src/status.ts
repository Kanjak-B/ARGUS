import type { NodeStatus } from './api'

/** Libellé et couleurs d'un statut, partagés par le graphe, les badges et la légende. */
export const STATUS: Record<NodeStatus, { label: string; color: string; badge: string }> = {
  ok: {
    label: 'Online',
    color: '#34d399',
    badge: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/30',
  },
  failed: {
    label: 'Failed',
    color: '#f87171',
    badge: 'bg-red-400/10 text-red-300 ring-red-400/30',
  },
  pending: {
    label: 'Pending',
    color: '#fbbf24',
    badge: 'bg-amber-400/10 text-amber-300 ring-amber-400/30',
  },
  unmanaged: {
    label: 'Unmanaged',
    color: '#94a3b8',
    badge: 'bg-slate-400/10 text-slate-300 ring-slate-400/30',
  },
}
