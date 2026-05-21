import { useState } from 'react'

/**
 * GroupRow — one requirement group, possibly with sub-groups.
 */
function GroupRow({ group, depth = 0 }) {
  const [expanded, setExpanded] = useState(!group.satisfied && depth === 0)
  const hasChildren = group.sub_statuses && group.sub_statuses.length > 0

  return (
    <div className={`group-row group-row--depth-${depth}`}>
      <div
        className={`group-row__header ${hasChildren ? 'group-row__header--clickable' : ''}`}
        onClick={() => hasChildren && setExpanded(v => !v)}
      >
        <span className={`group-row__icon ${group.satisfied ? 'group-row__icon--done' : 'group-row__icon--todo'}`}>
          {group.satisfied ? '✓' : '○'}
        </span>
        <span className="group-row__name">{group.group_name}</span>
        {!group.satisfied && group.credits_still_needed > 0 && (
          <span className="group-row__detail">{group.credits_still_needed} cr left</span>
        )}
        {!group.satisfied && group.courses_still_needed > 0 && group.credits_still_needed === 0 && (
          <span className="group-row__detail">{group.courses_still_needed} course{group.courses_still_needed !== 1 ? 's' : ''} left</span>
        )}
        {hasChildren && (
          <span className="group-row__chevron">{expanded ? '▾' : '▸'}</span>
        )}
      </div>

      {expanded && hasChildren && (
        <div className="group-row__children">
          {group.sub_statuses.map(sub => (
            <GroupRow key={sub.group_id} group={sub} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}


/**
 * ProgramStatus
 * Shows one collapsible card per target program with a checklist of
 * requirement groups (satisfied ✓ vs still needed ○).
 */
export default function ProgramStatus({ programStatuses }) {
  return (
    <section className="program-status">
      <h3 className="program-status__heading">Program Checklist</h3>
      {programStatuses.map(ps => (
        <ProgramCard key={ps.program_id} status={ps} />
      ))}
    </section>
  )
}

function ProgramCard({ status }) {
  const [open, setOpen] = useState(true)
  const doneCount = status.group_statuses.filter(g => g.satisfied).length
  const totalCount = status.group_statuses.length

  return (
    <div className={`program-card-status ${status.satisfied ? 'program-card-status--done' : ''}`}>
      <button className="program-card-status__header" onClick={() => setOpen(v => !v)}>
        <span className={`status-dot ${status.satisfied ? 'status-dot--done' : 'status-dot--todo'}`} />
        <span className="program-card-status__name">{status.program_name}</span>
        <span className="program-card-status__progress">
          {doneCount}/{totalCount} groups
        </span>
        <span className="program-card-status__chevron">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="program-card-status__body">
          {status.group_statuses.map(group => (
            <GroupRow key={group.group_id} group={group} depth={0} />
          ))}
        </div>
      )}
    </div>
  )
}
