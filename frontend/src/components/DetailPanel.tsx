import type { ReactNode } from 'react'
import type { GraphEdge, Topology } from '../api'
import { LAYERS } from '../layout'
import { CloseIcon } from './Icons'
import { StatusBadge } from './StatusBadge'
import type { Selection } from './TopologyGraph'

interface Props {
  topology: Topology
  selection: Selection
  onSelect: (selection: Selection | null) => void
}

function Panel({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string
  subtitle: string
  onClose: () => void
  children: ReactNode
}) {
  return (
    <aside className="panel flex max-h-full w-full flex-col overflow-hidden lg:w-80">
      <header className="flex items-start justify-between gap-3 border-b border-white/10 p-4">
        <div className="min-w-0">
          <p className="text-xs tracking-wider text-slate-500 uppercase">{subtitle}</p>
          <h2 className="truncate text-lg font-semibold text-white" title={title}>
            {title}
          </h2>
        </div>
        <button type="button" className="btn btn-ghost p-1.5" aria-label="Fermer" onClick={onClose}>
          <CloseIcon />
        </button>
      </header>
      <div className="space-y-4 overflow-y-auto p-4 text-sm">{children}</div>
    </aside>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-200">{children}</dd>
    </div>
  )
}

export function DetailPanel({ topology, selection, onSelect }: Props) {
  const labelOf = (id: string) => topology.nodes.find((node) => node.id === id)?.label ?? id
  const close = () => onSelect(null)

  if (selection.kind === 'edge') {
    const edge = topology.edges.find((e) => e.id === selection.id)
    if (!edge) return null
    return (
      <Panel title="Liaison" subtitle="Lien LLDP" onClose={close}>
        <dl className="space-y-3">
          <Field label={labelOf(edge.source)}>
            <code className="text-cyan-300">{edge.source_interface}</code>
          </Field>
          <Field label={labelOf(edge.target)}>
            <code className="text-cyan-300">{edge.target_interface}</code>
          </Field>
        </dl>
      </Panel>
    )
  }

  const node = topology.nodes.find((n) => n.id === selection.id)
  if (!node) return null

  // Chaque lien est présenté depuis le point de vue du nœud sélectionné
  const linksFrom = (edge: GraphEdge) => {
    const outgoing = edge.source === node.id
    return {
      id: edge.id,
      local: outgoing ? edge.source_interface : edge.target_interface,
      remote: outgoing ? edge.target_interface : edge.source_interface,
      neighbor: labelOf(outgoing ? edge.target : edge.source),
    }
  }
  const links = topology.edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map(linksFrom)
    .sort((a, b) => a.local.localeCompare(b.local, undefined, { numeric: true }))

  return (
    <Panel title={node.label} subtitle="Équipement" onClose={close}>
      <StatusBadge status={node.status} />
      <dl className="space-y-3">
        <Field label="Adresse IP">{node.ip ?? 'Inconnue'}</Field>
        <Field label="Couche">{LAYERS.find((layer) => layer.id === node.layer)?.label}</Field>
        {node.model && <Field label="Logiciel">{node.model}</Field>}
      </dl>
      {node.status === 'unmanaged' && (
        <p className="rounded-lg bg-white/5 p-3 text-xs text-slate-400">
          Ce voisin est annoncé par LLDP mais ne fait pas partie des équipements surveillés.
        </p>
      )}
      <section>
        <h3 className="mb-2 text-xs tracking-wider text-slate-500 uppercase">
          Liaisons ({links.length})
        </h3>
        <ul className="space-y-2">
          {links.map((link) => (
            <li key={link.id}>
              <button
                type="button"
                className="w-full rounded-lg border border-white/10 bg-white/5 p-3 text-left transition hover:border-cyan-400/40"
                onClick={() => onSelect({ kind: 'edge', id: link.id })}
              >
                <span className="block truncate font-medium text-slate-100">{link.neighbor}</span>
                <span className="font-mono text-xs text-slate-400">
                  {link.local} → {link.remote}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {links.length === 0 && <p className="text-xs text-slate-500">Aucune liaison connue.</p>}
      </section>
    </Panel>
  )
}
