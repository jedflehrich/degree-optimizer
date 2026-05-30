/**
 * SummaryBanner
 * Per-program progress bars + quick overall stats at the top of the results view.
 */

/**
 * Recursively estimate credits still needed across all leaf groups.
 *
 * Key cases:
 *  - ONE_OF group (courses_still_needed===1, no credits/missing, has children):
 *    only the cheapest child needs to be done → take MIN across children.
 *  - ALL_REQUIRED group with children: every child must be done → SUM children
 *    + 3 cr × own missing_required courses.
 *  - Leaf group: use credits_still_needed, then courses_still_needed, then
 *    missing_required (in that order — ONE_OF leaves set missing_required to ALL
 *    eligible options but courses_still_needed to 1, so we must check the latter
 *    first to avoid massive overcounting).
 */
function creditsLeft(gs) {
  if (gs.satisfied) return 0

  if (gs.sub_statuses && gs.sub_statuses.length > 0) {
    // Detect ONE_OF: no credit tracking, courses_still_needed===1, no direct
    // missing courses — student only needs to finish ONE child.
    const isOneOf =
      gs.credits_still_needed === 0 &&
      gs.courses_still_needed === 1 &&
      (!gs.missing_required || gs.missing_required.length === 0)

    const subCosts = gs.sub_statuses.map(creditsLeft)

    if (isOneOf) {
      // e.g. focus_area: only complete the cheapest focus area
      return Math.min(...subCosts)
    }

    // ALL_REQUIRED: every child + parent's own direct missing courses
    const childTotal = subCosts.reduce((a, b) => a + b, 0)
    const parentOwn  = (gs.missing_required || []).length * 3
    return childTotal + parentOwn
  }

  // Leaf group — NOTE: check courses_still_needed BEFORE missing_required.
  // ONE_OF leaves set missing_required = all eligible options (e.g. 4 courses)
  // but courses_still_needed = 1 (only need one).  Checking missing_required
  // first would return 4×3=12 cr instead of the correct 1×3=3 cr.
  if (gs.credits_still_needed > 0) return gs.credits_still_needed
  if (gs.courses_still_needed > 0) return gs.courses_still_needed * 3
  if (gs.missing_required && gs.missing_required.length > 0) return gs.missing_required.length * 3
  return 0
}

/**
 * Build a map: group_id → program_id, covering every group at every depth.
 * Used to convert a course's satisfies_groups list into a program count.
 */
function buildGroupToProgram(result) {
  const map = {}
  function traverse(gs, programId) {
    map[gs.group_id] = programId
    for (const ss of gs.sub_statuses || []) traverse(ss, programId)
  }
  for (const ps of result.program_statuses) {
    for (const gs of ps.group_statuses) traverse(gs, ps.program_id)
  }
  return map
}

export default function SummaryBanner({ result, plannedCourses = [] }) {
  const directCourses = result.recommended_courses.filter(c => !c.is_prereq_filler)
  const prereqCourses = result.recommended_courses.filter(c => c.is_prereq_filler)
  const overlapCourses = result.recommended_courses.filter(c => c.overlap_score > 1)

  const programNames = result.program_statuses.map(p => p.program_name).join(' + ')

  // Map every group_id to its owning program_id.
  const groupToProgram = buildGroupToProgram(result)

  // Sum planned credits per program using satisfies_groups on each planned course.
  const plannedCreditsByProgram = {}
  for (const c of plannedCourses) {
    const programs = new Set()
    for (const gid of (c.satisfies_groups || [])) {
      const pid = groupToProgram[gid]
      if (pid) programs.add(pid)
    }
    programs.forEach(pid => {
      plannedCreditsByProgram[pid] = (plannedCreditsByProgram[pid] || 0) + (c.credits || 3)
    })
  }

  return (
    <div className="summary-banner">
      <div className="summary-banner__title">
        <h2 className="summary-banner__heading">Your Plan: {programNames}</h2>
        <p className="summary-banner__sub">
          You've completed {result.completed_count} course{result.completed_count !== 1 ? 's' : ''}.
          Here's what's left.
        </p>
      </div>

      {/* ── Per-program progress bars ─────────────────────── */}
      {result.program_statuses.map(ps => {
        const total = ps.total_credits_required ?? 0
        if (total === 0) return null

        const remaining    = ps.group_statuses.reduce((sum, gs) => sum + creditsLeft(gs), 0)
        const completed    = Math.max(0, total - remaining)
        const plannedRaw   = plannedCreditsByProgram[ps.program_id] || 0
        const planned      = Math.min(remaining, plannedRaw) // can't spill past the gap

        const completedPct = Math.min(100, Math.round(completed / total * 100))
        const plannedPct   = Math.min(100 - completedPct, Math.round(planned / total * 100))

        const whatIfPct = Math.min(100, completedPct + plannedPct)

        return (
          <div key={ps.program_id} className="progress-block">
            <div className="progress-block__labels">
              <span className="progress-block__label">{ps.program_name}</span>
              <span className="progress-block__pct">
                {completedPct}%
                {plannedPct > 0 && (
                  <span className="progress-block__what-if"> → {whatIfPct}%</span>
                )}
              </span>
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={completedPct + plannedPct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div style={{ display: 'flex', height: '100%' }}>
                {completedPct > 0 && (
                  <div className="progress-bar__fill" style={{ width: `${completedPct}%` }} />
                )}
                {plannedPct > 0 && (
                  <div
                    className="progress-bar__fill progress-bar__fill--planned"
                    style={{ width: `${plannedPct}%` }}
                    title={`+${planned} planned credits`}
                  />
                )}
              </div>
            </div>
            <div className="progress-block__sub">
              ~{completed} of {total} credits completed
              {planned > 0 && (
                <> · <strong className="progress-planned-label">+{planned} planned</strong></>
              )}
              {remaining > 0 && (
                <> · <strong>{Math.max(0, remaining - planned)} credits remaining</strong></>
              )}
            </div>
          </div>
        )
      })}

      {/* ── Quick stats ─────────────────────────────────────── */}
      <div className="summary-stats">
        <div className="stat">
          <span className="stat__value">{directCourses.length}</span>
          <span className="stat__label">Courses needed</span>
        </div>
        <div className="stat stat--divider" />
        <div className="stat">
          <span className="stat__value">{result.total_additional_credits}</span>
          <span className="stat__label">Credits left</span>
        </div>
        <div className="stat stat--divider" />
        <div className="stat">
          <span className="stat__value stat__value--accent">{overlapCourses.length}</span>
          <span className="stat__label">Overlap courses</span>
        </div>
        {prereqCourses.length > 0 && (
          <>
            <div className="stat stat--divider" />
            <div className="stat">
              <span className="stat__value stat__value--muted">{prereqCourses.length}</span>
              <span className="stat__label">Prereq fillers</span>
            </div>
          </>
        )}
      </div>

      {result.ap_generic_credits_applied > 0 && (
        <div className="alert alert--info">
          <strong>{result.ap_generic_credits_applied} AP elective credit{result.ap_generic_credits_applied !== 1 ? 's' : ''} applied</strong>{' '}
          — your AP exams reduced your open-ended elective requirements above.
        </div>
      )}

      {result.unresolved_groups.length > 0 && (
        <div className="alert alert--warning">
          <strong>{result.unresolved_groups.length} open-ended requirement{result.unresolved_groups.length !== 1 ? 's' : ''}</strong>{' '}
          need manual selection (language requirement, electives, etc.). These are listed at the bottom.
        </div>
      )}
    </div>
  )
}
