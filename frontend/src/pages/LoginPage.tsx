import { useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import { EyeIcon } from '../components/Icons'

export function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.login(password)
      onLogin()
    } catch (e) {
      setError(errorMessage(e))
      setBusy(false)
    }
  }

  return (
    <main className="bg-grid relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div className="pointer-events-none absolute top-1/4 size-[32rem] rounded-full bg-cyan-500/10 blur-3xl" />
      <form onSubmit={submit} className="panel relative w-full max-w-sm p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-4 rounded-2xl bg-cyan-400/10 p-3 text-cyan-300 ring-1 ring-cyan-400/30">
            <EyeIcon className="size-8" />
          </span>
          <h1 className="text-2xl font-semibold tracking-[0.3em] text-white">ARGUS</h1>
          <p className="mt-1 text-sm text-slate-400">Network topology monitoring</p>
        </div>
        <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-300">
          Administrator password
        </label>
        <input
          id="password"
          type="password"
          className="field"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          autoFocus
        />
        {error && (
          <p role="alert" className="mt-2 text-sm text-red-300">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary mt-5 w-full" disabled={busy || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
