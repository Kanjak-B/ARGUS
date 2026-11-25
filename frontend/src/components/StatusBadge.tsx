import type { NodeStatus } from '../api'
import { STATUS } from '../status'

export function StatusBadge({ status }: { status: NodeStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS[status].badge}`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {STATUS[status].label}
    </span>
  )
}
