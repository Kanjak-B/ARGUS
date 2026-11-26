import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, errorMessage, type Change, type Device, type Topology } from './api'

const RECONNECT_AFTER_MS = 3000

/** Données de l'application, rechargées à chaque événement du flux temps réel (SSE). */
export function useArgusData(onUnauthorized: () => void) {
  const [devices, setDevices] = useState<Device[] | null>(null)
  const [topology, setTopology] = useState<Topology | null>(null)
  const [changes, setChanges] = useState<Change[]>([])
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)
  const latestRequest = useRef(0)

  const refresh = useCallback(async () => {
    const requestId = ++latestRequest.current
    try {
      const [nextDevices, nextTopology, nextChanges] = await Promise.all([
        api.devices(),
        api.topology(),
        api.changes(),
      ])
      // Une réponse en retard ne doit pas écraser une plus récente
      if (requestId !== latestRequest.current) return
      setDevices(nextDevices)
      setTopology(nextTopology)
      setChanges(nextChanges)
      setError(null)
    } catch (e) {
      if (requestId !== latestRequest.current) return
      if (e instanceof ApiError && e.status === 401) onUnauthorized()
      else setError(errorMessage(e))
    }
  }, [onUnauthorized])

  useEffect(() => {
    let source: EventSource
    let retry: number | undefined

    const connect = () => {
      source = new EventSource('/api/events')
      source.onopen = () => setLive(true)
      source.onmessage = () => void refresh()
      source.onerror = () => {
        setLive(false)
        // Signale la panne, ou renvoie vers la connexion si la session a expiré
        void refresh()
        // Après une réponse d'erreur, le navigateur abandonne : il faut rouvrir le flux
        if (source.readyState === EventSource.CLOSED) {
          window.clearTimeout(retry)
          retry = window.setTimeout(connect, RECONNECT_AFTER_MS)
        }
      }
    }

    void refresh()
    connect()
    return () => {
      window.clearTimeout(retry)
      source.close()
    }
  }, [refresh])

  return { devices, topology, changes, error, live, refresh }
}
