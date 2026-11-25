import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, errorMessage, type Device, type Topology } from './api'

const REFRESH_EVERY_MS = 3000

/** Équipements et topologie, rechargés périodiquement (remplacé par le flux SSE à l'étape 3). */
export function useArgusData(onUnauthorized: () => void) {
  const [devices, setDevices] = useState<Device[] | null>(null)
  const [topology, setTopology] = useState<Topology | null>(null)
  const [error, setError] = useState<string | null>(null)
  const latestRequest = useRef(0)

  const refresh = useCallback(async () => {
    const requestId = ++latestRequest.current
    try {
      const [nextDevices, nextTopology] = await Promise.all([api.devices(), api.topology()])
      // Une réponse en retard ne doit pas écraser une plus récente
      if (requestId !== latestRequest.current) return
      setDevices(nextDevices)
      setTopology(nextTopology)
      setError(null)
    } catch (e) {
      if (requestId !== latestRequest.current) return
      if (e instanceof ApiError && e.status === 401) onUnauthorized()
      else setError(errorMessage(e))
    }
  }, [onUnauthorized])

  useEffect(() => {
    let timer: number
    let stopped = false
    const poll = async () => {
      await refresh()
      if (!stopped) timer = window.setTimeout(poll, REFRESH_EVERY_MS)
    }
    void poll()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [refresh])

  return { devices, topology, error, refresh }
}
