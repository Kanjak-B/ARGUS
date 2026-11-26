export type DeviceStatus = 'ok' | 'failed' | 'pending'
export type NodeStatus = DeviceStatus | 'unmanaged'
export type Layer = 'core' | 'distribution' | 'access'

export interface Device {
  id: number
  ip: string
  hostname: string | null
  created_at: string
  status: DeviceStatus
  /** Couche choisie par l'administrateur ; null : détection automatique. */
  role: Layer | null
  layer: Layer
}

export interface GraphNode {
  id: string
  label: string
  status: NodeStatus
  layer: Layer
  ip: string | null
  model: string | null
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  source_interface: string
  target_interface: string
}

export interface Topology {
  nodes: GraphNode[]
  edges: GraphEdge[]
  scanned_at: string | null
  scanning: boolean
  last_error: string | null
  version: number
}

export type ChangeType =
  | 'device_added'
  | 'device_removed'
  | 'device_failed'
  | 'device_recovered'
  | 'device_renamed'
  | 'link_added'
  | 'link_removed'

export interface Change {
  id: number
  created_at: string
  type: ChangeType
  message: string
  details: { ip: string; device: string }
}

export const CHANGES_LIMIT = 200

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${url}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Serveur injoignable', 0)
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = typeof payload?.detail === 'string' ? payload.detail : null
    throw new ApiError(detail ?? `Erreur ${response.status}`, response.status)
  }

  // Une réponse 204 peut annoncer du JSON tout en ayant un corps vide
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const api = {
  login: (password: string) => request<void>('POST', '/login', { password }),
  logout: () => request<void>('POST', '/logout'),
  devices: () => request<Device[]>('GET', '/devices'),
  addDevice: (ip: string) => request<Device>('POST', '/devices', { ip }),
  deleteDevice: (id: number) => request<void>('DELETE', `/devices/${id}`),
  setRole: (id: number, role: Layer | null) => request<void>('PATCH', `/devices/${id}`, { role }),
  topology: () => request<Topology>('GET', '/topology'),
  changes: () => request<Change[]>('GET', `/changes?limit=${CHANGES_LIMIT}`),
  scan: () => request<void>('POST', '/scan'),
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Erreur inattendue'
}
