import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, CHANGES_LIMIT } from './api'
import {
  EyeIcon,
  HistoryIcon,
  LogoutIcon,
  NetworkIcon,
  ServerIcon,
} from './components/Icons'
import { DevicesPage } from './pages/DevicesPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { TopologyPage } from './pages/TopologyPage'
import { useArgusData } from './useArgusData'
import type { View } from './views'

const TABS = [
  { id: 'topology', label: 'Topologie', Icon: NetworkIcon },
  { id: 'devices', label: 'Équipements', Icon: ServerIcon },
  { id: 'history', label: 'Historique', Icon: HistoryIcon },
] as const

type Tab = (typeof TABS)[number]['id']
type Session = 'checking' | 'anonymous' | 'authenticated'

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>('topology')
  // Conservée ici pour retrouver le même onglet après un passage par une autre page
  const [view, setView] = useState<View>('all')
  const { devices, topology, changes, error, live, refresh } = useArgusData(onLogout)

  const logout = async () => {
    await api.logout().catch(() => {})
    onLogout()
  }

  return (
    <div className="flex min-h-screen flex-col md:h-screen md:flex-row">
      <nav className="flex shrink-0 items-center gap-2 border-b border-white/10 bg-slate-900/70 p-3 md:w-60 md:flex-col md:items-stretch md:border-r md:border-b-0 md:p-4">
        <div className="mr-auto flex items-center gap-3 md:mr-0 md:mb-6 md:px-2 md:pt-2">
          <span className="rounded-xl bg-cyan-400/10 p-2 text-cyan-300 ring-1 ring-cyan-400/30">
            <EyeIcon className="size-5" />
          </span>
          <span className="hidden text-lg font-semibold tracking-[0.25em] text-white sm:inline">
            ARGUS
          </span>
        </div>
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            aria-current={tab === id ? 'page' : undefined}
            aria-label={label}
            className={`btn justify-start ${tab === id ? 'bg-cyan-400/10 text-cyan-200 ring-1 ring-cyan-400/20' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
            onClick={() => setTab(id)}
          >
            <Icon />
            <span className={tab === id ? 'inline' : 'hidden sm:inline'}>{label}</span>
          </button>
        ))}
        <p
          role="status"
          className="flex items-center gap-2 px-2 text-xs text-slate-400 md:mt-auto md:px-4 md:py-2"
          title={live ? 'Mises à jour en direct' : 'Connexion au serveur interrompue'}
        >
          <span
            className={`size-2 shrink-0 rounded-full ${live ? 'animate-pulse bg-emerald-400' : 'bg-amber-400'}`}
          />
          <span className="sr-only md:not-sr-only">{live ? 'En direct' : 'Reconnexion…'}</span>
        </p>
        <button
          type="button"
          className="btn justify-start text-slate-400 hover:bg-white/5 hover:text-white"
          onClick={logout}
          aria-label="Se déconnecter"
        >
          <LogoutIcon />
          <span className="hidden md:inline">Se déconnecter</span>
        </button>
      </nav>

      <main className="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
        {error && (
          <p role="alert" className="mb-4 rounded-lg border border-amber-400/30 bg-amber-400/10 px-4 py-2 text-sm text-amber-200">
            {error} — les données affichées peuvent être anciennes.
          </p>
        )}
        {!devices || !topology ? (
          !error && <p className="text-sm text-slate-500">Chargement…</p>
        ) : tab === 'topology' ? (
          <TopologyPage
            devices={devices}
            topology={topology}
            view={view}
            onViewChange={setView}
            refresh={refresh}
            onManageDevices={() => setTab('devices')}
          />
        ) : tab === 'devices' ? (
          <DevicesPage devices={devices} refresh={refresh} />
        ) : (
          <HistoryPage changes={changes} limit={CHANGES_LIMIT} />
        )}
      </main>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState<Session>('checking')
  const toLogin = useCallback(() => setSession('anonymous'), [])

  // Un cookie de session encore valide évite de redemander le mot de passe
  useEffect(() => {
    api
      .devices()
      .then(() => setSession('authenticated'))
      .catch((e) =>
        setSession(e instanceof ApiError && e.status === 401 ? 'anonymous' : 'authenticated'),
      )
  }, [])

  if (session === 'checking') return null
  if (session === 'anonymous') return <LoginPage onLogin={() => setSession('authenticated')} />
  return <Dashboard onLogout={toLogin} />
}
