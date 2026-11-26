import type { Change, ChangeType } from '../api'
import { HistoryIcon } from '../components/Icons'

const KINDS: Record<ChangeType, { label: string; badge: string; dot: string }> = {
  device_failed: { label: 'Failure', badge: 'bg-red-400/10 text-red-300', dot: 'bg-red-400' },
  link_removed: { label: 'Link lost', badge: 'bg-red-400/10 text-red-300', dot: 'bg-red-400' },
  device_recovered: {
    label: 'Recovery',
    badge: 'bg-emerald-400/10 text-emerald-300',
    dot: 'bg-emerald-400',
  },
  link_added: {
    label: 'Link added',
    badge: 'bg-emerald-400/10 text-emerald-300',
    dot: 'bg-emerald-400',
  },
  device_added: { label: 'Added', badge: 'bg-cyan-400/10 text-cyan-300', dot: 'bg-cyan-400' },
  device_removed: {
    label: 'Removed',
    badge: 'bg-slate-400/10 text-slate-300',
    dot: 'bg-slate-400',
  },
  device_renamed: {
    label: 'Renamed',
    badge: 'bg-amber-400/10 text-amber-300',
    dot: 'bg-amber-400',
  },
}

function groupByDay(changes: Change[]) {
  const days = new Map<string, Change[]>()
  for (const change of changes) {
    const day = new Date(change.created_at).toLocaleDateString('en-GB', { dateStyle: 'full' })
    days.set(day, [...(days.get(day) ?? []), change])
  }
  return [...days]
}

export function HistoryPage({ changes, limit }: { changes: Change[]; limit: number }) {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-white">History</h1>
        <p className="text-sm text-slate-400">
          Changes detected on the network, newest first.
        </p>
      </header>

      {changes.length === 0 ? (
        <div className="panel flex flex-col items-center gap-2 p-10 text-center">
          <HistoryIcon className="size-10 text-slate-600" />
          <p className="text-sm text-slate-400">No changes recorded yet.</p>
          <p className="text-xs text-slate-500">The first scan is used as the baseline.</p>
        </div>
      ) : (
        groupByDay(changes).map(([day, entries]) => (
          <section key={day}>
            <h2 className="mb-2 text-xs tracking-wider text-slate-400 uppercase">{day}</h2>
            <ol className="panel divide-y divide-white/5">
              {entries.map((change) => {
                const kind = KINDS[change.type]
                return (
                  <li key={change.id} className="flex items-start gap-3 px-4 py-3 text-sm">
                    <span className={`mt-1.5 size-2 shrink-0 rounded-full ${kind.dot}`} />
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-slate-100">{change.message}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className={`rounded-full px-2 py-0.5 font-medium ${kind.badge}`}>
                          {kind.label}
                        </span>
                        <span className="font-mono">{change.details.ip}</span>
                      </p>
                    </div>
                    <time
                      className="shrink-0 text-xs text-slate-500 tabular-nums"
                      dateTime={change.created_at}
                    >
                      {new Date(change.created_at).toLocaleTimeString('en-GB')}
                    </time>
                  </li>
                )
              })}
            </ol>
          </section>
        ))
      )}

      {changes.length >= limit && (
        <p className="text-center text-xs text-slate-500">
          Only the {limit} most recent changes are shown.
        </p>
      )}
    </div>
  )
}
