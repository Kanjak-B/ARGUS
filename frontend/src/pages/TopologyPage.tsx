import { useRef, useState } from 'react'
import { api, errorMessage, type Device, type NodeStatus, type Topology } from '../api'
import { DetailPanel } from '../components/DetailPanel'
import { DownloadIcon, NetworkIcon, PlusIcon, RefreshIcon } from '../components/Icons'
import { TopologyGraph, type GraphHandle, type Selection } from '../components/TopologyGraph'
import { STATUS } from '../status'

interface Props {
  devices: Device[]
  topology: Topology
  refresh: () => Promise<void>
  onManageDevices: () => void
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="panel px-5 py-4">
      <p className="text-xs tracking-wider text-slate-400 uppercase">{label}</p>
      <p className={`mt-1 text-3xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

function ExportLink({ format, label, enabled }: { format: string; label: string; enabled: boolean }) {
  const content = (
    <>
      <DownloadIcon />
      {label}
    </>
  )
  return enabled ? (
    <a className="btn btn-ghost" href={`/api/export/${format}`} download>
      {content}
    </a>
  ) : (
    <span className="btn btn-ghost opacity-50" aria-disabled="true">
      {content}
    </span>
  )
}

export function TopologyPage({ devices, topology, refresh, onManageDevices }: Props) {
  const [selection, setSelection] = useState<Selection | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const [imageError, setImageError] = useState<string | null>(null)
  const graphRef = useRef<GraphHandle>(null)

  const hasOnlineNode = topology.nodes.some((node) => node.status === 'ok')

  const downloadImage = async () => {
    const date = new Date(topology.scanned_at!)
    // Format AAAAMMJJ_HHMMSS en heure locale, comme les exports Excel et JSON
    const stamp = date.toLocaleString('sv-SE').replace(/[-:]/g, '').replace(' ', '_')
    try {
      await graphRef.current!.downloadPng(
        `ARGUS — équipements en ligne — ${date.toLocaleString('fr-FR')}`,
        `topology_${stamp}.png`,
      )
      setImageError(null)
    } catch (e) {
      setImageError(errorMessage(e))
    }
  }

  const online = devices.filter((d) => d.status === 'ok').length
  const failed = devices.filter((d) => d.status === 'failed').length

  const scan = async () => {
    try {
      await api.scan()
      setScanError(null)
      await refresh()
    } catch (e) {
      setScanError(errorMessage(e))
    }
  }

  const lastScan = topology.scanned_at
    ? `Dernier scan : ${new Date(topology.scanned_at).toLocaleString('fr-FR')}`
    : 'Aucun scan pour le moment'
  const problem = imageError ?? scanError ?? (topology.last_error && `Dernier scan : ${topology.last_error}`)

  return (
    <div className="flex h-full flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Topologie</h1>
          <p className="text-sm text-slate-400">{lastScan}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-ghost"
            title="Image des équipements qui répondent et de leurs liaisons"
            onClick={downloadImage}
            disabled={!topology.scanned_at || !hasOnlineNode}
          >
            <DownloadIcon />
            Image PNG
          </button>
          <ExportLink format="xlsx" label="Excel" enabled={Boolean(topology.scanned_at)} />
          <ExportLink format="json" label="JSON" enabled={Boolean(topology.scanned_at)} />
          <button type="button" className="btn btn-primary" onClick={scan} disabled={topology.scanning}>
            <RefreshIcon className={`size-4 ${topology.scanning ? 'animate-spin' : ''}`} />
            {topology.scanning ? 'Scan en cours…' : 'Scanner'}
          </button>
        </div>
      </header>

      {problem && (
        <p role="alert" className="rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-2 text-sm text-red-300">
          {problem}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Équipements" value={devices.length} tone="text-white" />
        <Stat label="En ligne" value={online} tone="text-emerald-300" />
        <Stat label="En échec" value={failed} tone={failed ? 'text-red-300' : 'text-slate-500'} />
        <Stat label="Liaisons" value={topology.edges.length} tone="text-cyan-300" />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
        <section className="panel relative min-h-[26rem] flex-1 overflow-hidden" aria-label="Graphe du réseau">
          {topology.nodes.length === 0 ? (
            <div className="bg-grid flex size-full min-h-[26rem] flex-col items-center justify-center gap-3 p-6 text-center">
              <NetworkIcon className="size-12 text-slate-600" />
              <p className="text-lg font-medium text-white">Aucun équipement à afficher</p>
              <p className="max-w-sm text-sm text-slate-400">
                Ajoute l'adresse IP d'un premier équipement pour découvrir ton réseau.
              </p>
              <button type="button" className="btn btn-primary" onClick={onManageDevices}>
                <PlusIcon />
                Ajouter un équipement
              </button>
            </div>
          ) : (
            <>
              <div className="absolute inset-0">
                <TopologyGraph
                  ref={graphRef}
                  topology={topology}
                  selection={selection}
                  onSelect={setSelection}
                />
              </div>
              <ul className="pointer-events-none absolute bottom-3 left-3 flex max-w-[70%] flex-wrap gap-x-4 gap-y-1 rounded-lg bg-slate-900/90 px-3 py-2 text-xs text-slate-300">
                {(Object.keys(STATUS) as NodeStatus[]).map((status) => (
                  <li key={status} className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full" style={{ background: STATUS[status].color }} />
                    {STATUS[status].label}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
        {selection && (
          <DetailPanel topology={topology} selection={selection} onSelect={setSelection} />
        )}
      </div>
    </div>
  )
}
