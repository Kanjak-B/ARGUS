import type { Layer, Topology } from './api'

export const LAYERS: { id: Layer; label: string }[] = [
  { id: 'core', label: 'Cœur' },
  { id: 'distribution', label: 'Distribution' },
  { id: 'access', label: 'Accès' },
]

const COLUMN_WIDTH = 230
const ROW_HEIGHT = 230
const LABEL_MARGIN = 190
const SWEEPS = 4

export interface Point {
  x: number
  y: number
}

export interface HierarchicalLayout {
  /** Position de chaque nœud, par identifiant d'équipement. */
  nodes: Map<string, Point>
  /** Titre de chaque rangée occupée. */
  labels: { layer: Layer; text: string; position: Point }[]
}

/**
 * Une rangée par couche. Dans chaque rangée, les nœuds sont rapprochés de leurs voisins des
 * autres rangées (barycentre) pour limiter les croisements. Le résultat est déterministe.
 */
export function hierarchicalLayout({ nodes, edges }: Topology): HierarchicalLayout {
  const rows = LAYERS.map(({ id, label }) => ({
    layer: id,
    label,
    ids: nodes
      .filter((node) => node.layer === id)
      .map((node) => node.id)
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
  })).filter((row) => row.ids.length > 0)

  const rowOf = new Map(rows.flatMap((row, index) => row.ids.map((id) => [id, index] as const)))
  const x = new Map<string, number>()
  const place = (ids: string[]) =>
    ids.forEach((id, index) => x.set(id, (index - (ids.length - 1) / 2) * COLUMN_WIDTH))
  rows.forEach((row) => place(row.ids))

  const neighbors = (id: string) =>
    edges.flatMap((edge) => {
      const other = edge.source === id ? edge.target : edge.target === id ? edge.source : null
      return other !== null && rowOf.get(other) !== rowOf.get(id) ? [other] : []
    })

  for (let sweep = 0; sweep < SWEEPS; sweep++) {
    // Alternance haut vers bas puis bas vers haut
    for (const row of sweep % 2 === 0 ? rows : [...rows].reverse()) {
      const score = new Map(
        row.ids.map((id) => {
          const linked = neighbors(id)
          const sum = linked.reduce((total, other) => total + x.get(other)!, 0)
          return [id, linked.length ? sum / linked.length : x.get(id)!] as const
        }),
      )
      row.ids.sort((a, b) => score.get(a)! - score.get(b)!)
      place(row.ids)
    }
  }

  const left = Math.min(...x.values()) - LABEL_MARGIN
  return {
    nodes: new Map(
      rows.flatMap((row, index) =>
        row.ids.map((id) => [id, { x: x.get(id)!, y: index * ROW_HEIGHT }] as const),
      ),
    ),
    labels: rows.map((row, index) => ({
      layer: row.layer,
      text: row.label.toUpperCase(),
      position: { x: left, y: index * ROW_HEIGHT },
    })),
  }
}
