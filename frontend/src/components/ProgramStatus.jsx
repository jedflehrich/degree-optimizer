import { useState, useMemo } from 'react'

const MAX_VISIBLE = 3   // show this many courses before "... N more"

/**
 * True when a group is ONE_OF type with multiple child options.
 * Detected by: courses_still_needed===1, no credit tracking, no direct missing
 * required courses, and more than one child sub-status.
 * Mirrors the identical helper in RequirementsPanel.jsx.
 */
function isOneOfWithOptions(group) {
  return (
    group.courses_still_needed === 1 &&
    group.credits_still_needed === 0 &&
    (!group.missing_required || group.missing_required.length === 0) &&
    group.sub_statuses && group.sub_statuses.length > 1
  )
}

/**
 * Returns true when every leaf under `group` is either backend-satisfied or
 * has a planned course (in plannedGroupIds).  This lets parent rows like
 * "Probability and Statistics" show ✓ as soon as all their children are done
 * or selected — even though the parent group_id never appears in a course's
 * satisfies_groups list.
 *
 * ONE_OF groups (e.g. focus_area) only need ONE child to be fully planned,
 * not all of them — mirrors SummaryBanner's creditsLeft ONE_OF logic.
 *
 * MIXED groups (e.g. foundational_ds) have BOTH sub_statuses AND their own
 * direct missing_required courses (e.g. STAT 240/340/CS 320).  Both the
 * sub-groups AND the parent's own courses must be planned for the group to
 * count as fully planned.
 */
function isGroupFullyPlanned(group, plannedGroupIds) {
  if (group.satisfied) return true
  if (group.sub_statuses && group.sub_statuses.length > 0) {
    if (isOneOfWithOptions(group)) {
      // Only ONE sub-group needs to be planned (e.g. any one focus area)
      return group.sub_statuses.some(sub => isGroupFullyPlanned(sub, plannedGroupIds))
    }
    // All sub-groups must be planned
    if (!group.sub_statuses.every(sub => isGroupFullyPlanned(sub, plannedGroupIds))) return false
    // If this non-leaf group ALSO has its own direct required courses
    // (missing_required at the parent level), those must be planned too.
    // The optimizer gives these courses satisfies_groups = [group.group_id],
    // so plannedGroupIds.has(group.group_id) becomes true when they're selected.
    if (group.missing_required && group.missing_required.length > 0) {
      return plannedGroupIds?.has(group.group_id) ?? false
    }
    return true
  }
  // Leaf group: planned if the student selected a course that satisfies it.
  return plannedGroupIds?.has(group.group_id) ?? false
}

/**
 * GroupRow — one requirement group with optional course list.
 *
 * plannedGroupIds: Set of group IDs that have at least one course selected by
 * the student in the requirements panel. Used to show a green checkmark for
 * groups the student has planned to satisfy (but hasn't completed yet).
 */
function GroupRow({ group, depth = 0, plannedGroupIds }) {
  const [expanded,      setExpanded]      = useState(!group.satisfied && depth === 0)
  const [showAllCourses, setShowAllCourses] = useState(false)

  const hasChildren = group.sub_statuses && group.sub_statuses.length > 0

  // Courses to show as options (eligible but not yet taken)
  const eligible   = group.eligible_remaining || []
  const missing    = group.missing_required   || []
  const allOptions = [...new Set([...missing, ...eligible])]
  const visible    = showAllCourses ? allOptions : allOptions.slice(0, MAX_VISIBLE)
  const hiddenCount = allOptions.length - MAX_VISIBLE

  // A group is "planned" when all its descendants are either satisfied or selected.
  const isPlanned = !group.satisfied && isGroupFullyPlanned(group, plannedGroupIds)

  const iconClass = group.satisfied
    ? 'group-row__icon--done'
    : isPlanned
      ? 'group-row__icon--planned'
      : 'group-row__icon--todo'

  const icon = group.satisfied ? '✓' : isPlanned ? '✓' : '○'

  return (
    <div className={`group-row group-row--depth-${depth}`}>
      <div
        className={`group-row__header ${hasChildren ? 'group-row__header--clickable' : ''}`}
        onClick={() => hasChildren && setExpanded(v => !v)}
      >
        <span className={`group-row__icon ${iconClass}`}>{icon}</span>
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

      {/* Course options for unsatisfied groups */}
      {!group.satisfied && !hasChildren && allOptions.length > 0 && (
        <div className="group-row__options">
          {visible.map(id => (
            <span key={id} className="group-option">
              {id.replace(/_/g, ' ')}
            </span>
          ))}
          {!showAllCourses && hiddenCount > 0 && (
            <button
              className="group-option group-option--more"
              onClick={e => { e.stopPropagation(); setShowAllCourses(true) }}
            >
              ··· {hiddenCount} more
            </button>
          )}
          {showAllCourses && hiddenCount > 0 && (
            <button
              className="group-option group-option--more"
              onClick={e => { e.stopPropagation(); setShowAllCourses(false) }}
            >
              Show fewer
            </button>
          )}
        </div>
      )}

      {/* Sub-groups */}
      {expanded && hasChildren && (
        <div className="group-row__children">
          {group.sub_statuses.map(sub => (
            <GroupRow key={sub.group_id} group={sub} depth={depth + 1} plannedGroupIds={plannedGroupIds} />
          ))}
        </div>
      )}
    </div>
  )
}


/**
 * ProgramStatus
 * Collapsible checklist per target program.
 *
 * plannedCourses: CourseRecommendation[] of courses the student has selected
 * in the requirements panel. Used to show yellow checkmarks for planned groups.
 */
export default function ProgramStatus({ programStatuses, plannedCourses = [] }) {
  // Build the set of group IDs touched by any planned course.
  const plannedGroupIds = useMemo(() => {
    const ids = new Set()
    for (const c of plannedCourses) {
      for (const gid of (c.satisfies_groups || [])) ids.add(gid)
    }
    return ids
  }, [plannedCourses])

  return (
    <section className="program-status">
      <h3 className="program-status__heading">Program Checklist</h3>
      {plannedGroupIds.size > 0 && (
        <p className="program-status__legend">
          <span className="group-row__icon group-row__icon--planned">✓</span> Planned by your selections
        </p>
      )}
      {programStatuses.map(ps => (
        <ProgramCard key={ps.program_id} status={ps} plannedGroupIds={plannedGroupIds} />
      ))}
    </section>
  )
}

function ProgramCard({ status, plannedGroupIds }) {
  const [open, setOpen] = useState(true)
  const doneCount    = status.group_statuses.filter(g => g.satisfied).length
  const plannedCount = status.group_statuses.filter(g => !g.satisfied && isGroupFullyPlanned(g, plannedGroupIds)).length
  const totalCount   = status.group_statuses.length

  return (
    <div className={`program-card-status ${status.satisfied ? 'program-card-status--done' : ''}`}>
      <button className="program-card-status__header" onClick={() => setOpen(v => !v)}>
        <span className={`status-dot ${status.satisfied ? 'status-dot--done' : 'status-dot--todo'}`} />
        <span className="program-card-status__name">{status.program_name}</span>
        <span className="program-card-status__progress">
          {doneCount}/{totalCount} done
          {plannedCount > 0 && <span className="program-card-status__planned"> · {plannedCount} planned</span>}
        </span>
        <span className="program-card-status__chevron">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="program-card-status__body">
          {status.group_statuses.map(group => (
            <GroupRow key={group.group_id} group={group} depth={0} plannedGroupIds={plannedGroupIds} />
          ))}
        </div>
      )}
    </div>
  )
}
