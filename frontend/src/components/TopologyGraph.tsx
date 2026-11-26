import cytoscape, {
  type Core,
  type ElementDefinition,
  type NodeSingular,
  type Position,
} from 'cytoscape'
import { useEffect, useImperativeHandle, useRef, type Ref } from 'react'
import type { Topology } from '../api'
import { exportPng } from '../exportPng'
import { hierarchicalLayout, type HierarchicalLayout } from '../layout'
import { STATUS } from '../status'
import type { View } from '../views'
import { FitIcon, LayoutIcon } from './Icons'

export interface Selection {
  kind: 'node' | 'edge'
  id: string
}

export interface GraphHandle {
  downloadPng: (caption: string, filename: string) => Promise<void>
}

interface Props {
  /** Chaque vue conserve ses positions. Changer de vue exige un nouveau composant. */
  view: View
  topology: Topology
  selection: Selection | null
  onSelect: (selection: Selection | null) => void
  ref?: Ref<GraphHandle>
}

// Positions conservées entre deux affichages d'une vue, tant que sa structure est la même
const savedLayouts = new Map<View, { structure: string; positions: Map<string, Position> }>()

function switchIcon(color: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="10" rx="2"/><path d="M7 12h.01M10.5 12h.01M14 12h.01M17.5 12h.01"/></svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

// Les préfixes évitent qu'un nom d'équipement entre en collision avec l'identifiant d'un lien
function toElements({ nodes, edges }: Topology, layout: HierarchicalLayout): ElementDefinition[] {
  return [
    ...layout.labels.map((label) => ({
      group: 'nodes' as const,
      data: { id: `layer:${label.layer}`, layerTitle: label.layer, label: label.text },
      position: { ...label.position },
      selectable: false,
      grabbable: false,
    })),
    ...nodes.map((node) => ({
      group: 'nodes' as const,
      data: {
        id: `node:${node.id}`,
        ref: node.id,
        label: node.label,
        layer: node.layer,
        status: node.status,
        color: STATUS[node.status].color,
        icon: switchIcon(STATUS[node.status].color),
      },
      position: { ...layout.nodes.get(node.id)! },
    })),
    ...edges.map((edge) => ({
      group: 'edges' as const,
      data: {
        id: `edge:${edge.id}`,
        ref: edge.id,
        source: `node:${edge.source}`,
        target: `node:${edge.target}`,
        sourceLabel: edge.source_interface,
        targetLabel: edge.target_interface,
      },
    })),
  ]
}

/** Change dès qu'un nœud, un lien ou une couche change : le graphe est alors replacé. */
function structureOf({ nodes, edges }: Topology) {
  return JSON.stringify([
    nodes.map((node) => `${node.id}/${node.layer}`).sort(),
    edges.map((edge) => edge.id).sort(),
  ])
}

/** Fait passer par-dessus la rangée les liens entre deux nœuds non voisins d'une même couche. */
function bendLongLinks(cy: Core) {
  const devices = cy.nodes('[layer]').toArray() as NodeSingular[]
  let bent = 0
  cy.edges().forEach((edge) => {
    const source = edge.source()
    const target = edge.target()
    const from = source.position()
    const to = target.position()
    const crossesNode =
      source.data('layer') === target.data('layer') &&
      devices.some((node) => {
        const { x, y } = node.position()
        return (
          Math.abs(y - from.y) < 30 &&
          x > Math.min(from.x, to.x) + 1 &&
          x < Math.max(from.x, to.x) - 1
        )
      })
    edge.removeStyle()
    if (!crossesNode) return
    const height = 110 + 45 * bent++
    edge.style({
      'curve-style': 'unbundled-bezier',
      // Le signe dépend du sens du lien : l'arc doit toujours passer au-dessus
      'control-point-distances': from.x < to.x ? -height : height,
      'control-point-weights': 0.5,
    })
  })
}

function createGraph(container: HTMLElement) {
  return cytoscape({
    container,
    minZoom: 0.2,
    maxZoom: 2.5,
    style: [
      {
        selector: 'node',
        style: {
          width: 46,
          height: 46,
          shape: 'round-rectangle',
          'background-color': '#0f172a',
          'background-width': '68%',
          'background-height': '68%',
          'border-width': 2,
          'underlay-opacity': 0.1,
          'underlay-padding': 8,
          'underlay-shape': 'round-rectangle',
          label: 'data(label)',
          color: '#e2e8f0',
          'font-size': 12,
          'font-weight': 600,
          'text-valign': 'bottom',
          'text-margin-y': 12,
          'text-background-color': '#0b1120',
          'text-background-opacity': 0.85,
          'text-background-padding': '2px',
        },
      },
      {
        // Les titres de rangée n'ont ni icône ni couleur
        selector: 'node[color]',
        style: {
          'background-image': 'data(icon)',
          'border-color': 'data(color)',
          'underlay-color': 'data(color)',
        },
      },
      {
        selector: 'node[status = "unmanaged"]',
        style: { 'border-style': 'dashed', 'underlay-opacity': 0, width: 40, height: 40 },
      },
      { selector: 'node[status = "failed"]', style: { 'underlay-opacity': 0.28 } },
      {
        selector: 'node[layerTitle]',
        style: {
          width: 1,
          height: 1,
          'background-opacity': 0,
          'border-width': 0,
          'underlay-opacity': 0,
          'text-background-opacity': 0,
          'text-valign': 'center',
          'text-margin-y': 0,
          color: '#64748b',
          'font-size': 13,
          events: 'no',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 2,
          'line-color': '#334155',
          'curve-style': 'bezier',
          'control-point-step-size': 70,
          'source-label': 'data(sourceLabel)',
          'target-label': 'data(targetLabel)',
          'source-text-offset': 48,
          'target-text-offset': 48,
          color: '#94a3b8',
          'font-size': 9,
          'text-background-color': '#0f172a',
          'text-background-opacity': 0.92,
          'text-background-padding': '3px',
          'text-background-shape': 'roundrectangle',
        },
      },
      { selector: 'node:selected', style: { 'border-width': 4, 'underlay-opacity': 0.35 } },
      { selector: 'edge:selected', style: { width: 4, 'line-color': '#22d3ee' } },
    ],
  })
}

// Sans plafond, un petit réseau serait agrandi de façon démesurée
function fitGraph(cy: Core) {
  cy.fit(undefined, 50)
  if (cy.zoom() > 1.15) {
    cy.zoom(1.15)
    cy.center()
  }
}

function savePositions(cy: Core, view: View, structure: string) {
  const positions = new Map<string, Position>()
  cy.nodes().forEach((node) => {
    positions.set(node.id(), { ...node.position() })
  })
  savedLayouts.set(view, { structure, positions })
}

export function TopologyGraph({ view, topology, selection, onSelect, ref }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Core | null>(null)
  const structureRef = useRef<string | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useImperativeHandle(
    ref,
    () => ({
      downloadPng: (caption, filename) => exportPng(graphRef.current!, caption, filename),
    }),
    [],
  )

  useEffect(() => {
    const cy = createGraph(containerRef.current!)
    graphRef.current = cy
    structureRef.current = null
    cy.on('tap', (event) => {
      if (event.target === cy) onSelectRef.current(null)
    })
    cy.on('tap', 'node[ref], edge', (event) => {
      const element = event.target
      onSelectRef.current({ kind: element.isNode() ? 'node' : 'edge', id: element.data('ref') })
    })
    cy.on('dragfree', () => {
      savePositions(cy, view, structureRef.current!)
      bendLongLinks(cy)
    })

    // Le panneau de détails modifie la largeur : le réseau doit rester entièrement visible
    const observer = new ResizeObserver(() => {
      cy.resize()
      fitGraph(cy)
    })
    observer.observe(containerRef.current!)

    return () => {
      observer.disconnect()
      cy.destroy()
      graphRef.current = null
    }
  }, [view])

  useEffect(() => {
    const cy = graphRef.current!
    const elements = toElements(topology, hierarchicalLayout(topology))
    const structure = structureOf(topology)

    if (structure === structureRef.current) {
      // Même réseau : seules les données (états, noms) changent, rien ne bouge
      for (const element of elements) cy.getElementById(element.data.id!).data(element.data)
      return
    }

    const saved = savedLayouts.get(view)
    const restored = saved?.structure === structure ? saved.positions : undefined
    cy.batch(() => {
      cy.elements().remove()
      cy.add(
        elements.map((element) => {
          const position = restored?.get(element.data.id!)
          return position ? { ...element, position: { ...position } } : element
        }),
      )
    })
    structureRef.current = structure
    savePositions(cy, view, structure)
    bendLongLinks(cy)
    fitGraph(cy)
  }, [topology, view])

  useEffect(() => {
    const cy = graphRef.current!
    cy.elements().unselect()
    if (selection) cy.getElementById(`${selection.kind}:${selection.id}`).select()
  }, [selection, topology])

  const resetLayout = () => {
    const cy = graphRef.current
    if (!cy) return
    cy.batch(() => {
      for (const element of toElements(topology, hierarchicalLayout(topology))) {
        if (element.position) cy.getElementById(element.data.id!).position({ ...element.position })
      }
    })
    savePositions(cy, view, structureRef.current!)
    bendLongLinks(cy)
    fitGraph(cy)
  }

  return (
    <div className="relative size-full">
      {/* Cytoscape force « position: relative » : la taille ne doit pas dépendre de la position */}
      <div ref={containerRef} className="bg-grid size-full" />
      <div className="absolute right-3 bottom-3 flex gap-2">
        <button
          type="button"
          className="btn btn-ghost bg-slate-900/90 px-2.5"
          title="Rétablir la disposition hiérarchique"
          aria-label="Rétablir la disposition hiérarchique"
          onClick={resetLayout}
        >
          <LayoutIcon />
        </button>
        <button
          type="button"
          className="btn btn-ghost bg-slate-900/90 px-2.5"
          title="Ajuster à l'écran"
          aria-label="Ajuster à l'écran"
          onClick={() => graphRef.current && fitGraph(graphRef.current)}
        >
          <FitIcon />
        </button>
      </div>
    </div>
  )
}
