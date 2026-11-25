import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, errorMessage, type Device, type Layer } from '../api'
import { PlusIcon, ServerIcon, TrashIcon } from '../components/Icons'
import { StatusBadge } from '../components/StatusBadge'
import { LAYERS } from '../layout'

interface Props {
  devices: Device[]
  refresh: () => Promise<void>
}

function ConfirmDelete({
  device,
  onCancel,
  onConfirm,
}: {
  device: Device
  onCancel: () => void
  onConfirm: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!dialogRef.current?.open) dialogRef.current?.showModal()
  }, [])

  return (
    <dialog
      ref={dialogRef}
      className="panel m-auto w-[min(26rem,90vw)] bg-slate-900 p-6 text-slate-200 backdrop:bg-black/60"
      onCancel={onCancel}
    >
      <h2 className="text-lg font-semibold text-white">Supprimer l'équipement ?</h2>
      <p className="mt-2 text-sm text-slate-400">
        <strong className="text-slate-200">{device.hostname ?? device.ip}</strong> ({device.ip}) ne
        sera plus surveillé.
      </p>
      <div className="mt-6 flex justify-end gap-2">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Annuler
        </button>
        <button type="button" className="btn bg-red-500 text-white hover:bg-red-400" onClick={onConfirm}>
          Supprimer
        </button>
      </div>
    </dialog>
  )
}

export function DevicesPage({ devices, refresh }: Props) {
  const [ip, setIp] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toDelete, setToDelete] = useState<Device | null>(null)

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await action()
      setError(null)
      await refresh()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const add = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await api.addDevice(ip.trim())
      setIp('')
    })
  }

  const confirmDelete = () => {
    const device = toDelete!
    setToDelete(null)
    void run(() => api.deleteDevice(device.id))
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-white">Équipements</h1>
        <p className="text-sm text-slate-400">
          Équipements Cisco IOS interrogés par ARGUS. Les identifiants SSH viennent du fichier .env.
        </p>
      </header>

      <form onSubmit={add} className="panel p-4">
        <label htmlFor="ip" className="mb-2 block text-sm font-medium text-slate-300">
          Ajouter un équipement
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="ip"
            className="field font-mono"
            placeholder="Adresse IP, par exemple 10.0.0.1"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            maxLength={64}
            autoComplete="off"
            spellCheck={false}
            aria-invalid={error ? true : undefined}
          />
          <button type="submit" className="btn btn-primary shrink-0" disabled={busy || !ip.trim()}>
            <PlusIcon />
            Ajouter
          </button>
        </div>
        {error && (
          <p role="alert" className="mt-2 text-sm text-red-300">
            {error}
          </p>
        )}
      </form>

      <div className="panel overflow-x-auto">
        {devices.length === 0 ? (
          <div className="flex flex-col items-center gap-2 p-10 text-center">
            <ServerIcon className="size-10 text-slate-600" />
            <p className="text-sm text-slate-400">Aucun équipement enregistré.</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs tracking-wider text-slate-500 uppercase">
              <tr>
                <th className="px-5 py-3 font-medium">Nom</th>
                <th className="px-5 py-3 font-medium">Adresse IP</th>
                <th className="px-5 py-3 font-medium">Couche</th>
                <th className="px-5 py-3 font-medium">Statut</th>
                <th className="px-5 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {devices.map((device) => (
                <tr key={device.id} className="transition hover:bg-white/5">
                  <td className="px-5 py-3 font-medium text-white">
                    {device.hostname ?? <span className="text-slate-500">À découvrir</span>}
                  </td>
                  <td className="px-5 py-3 font-mono text-slate-300">{device.ip}</td>
                  <td className="px-5 py-3">
                    <select
                      className="field w-auto min-w-44 py-1.5"
                      aria-label={`Couche de ${device.hostname ?? device.ip}`}
                      value={device.role ?? ''}
                      disabled={busy}
                      onChange={(e) => {
                        const role = (e.target.value || null) as Layer | null
                        void run(() => api.setRole(device.id, role))
                      }}
                    >
                      <option value="">
                        Auto
                        {!device.role && ` (${LAYERS.find((l) => l.id === device.layer)?.label})`}
                      </option>
                      {LAYERS.map((layer) => (
                        <option key={layer.id} value={layer.id}>
                          {layer.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={device.status} />
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      type="button"
                      className="btn btn-ghost p-2 hover:text-red-300"
                      aria-label={`Supprimer ${device.ip}`}
                      title="Supprimer"
                      disabled={busy}
                      onClick={() => setToDelete(device)}
                    >
                      <TrashIcon />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {toDelete && (
        <ConfirmDelete device={toDelete} onCancel={() => setToDelete(null)} onConfirm={confirmDelete} />
      )}
    </div>
  )
}
