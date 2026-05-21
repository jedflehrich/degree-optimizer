/**
 * SummaryBanner
 * Three quick stats at the top of the results view.
 */
export default function SummaryBanner({ result }) {
  const directCourses = result.recommended_courses.filter(c => !c.is_prereq_filler)
  const prereqCourses = result.recommended_courses.filter(c => c.is_prereq_filler)
  const overlapCourses = result.recommended_courses.filter(c => c.overlap_score > 1)

  const programNames = result.program_statuses.map(p => p.program_name).join(' + ')

  return (
    <div className="summary-banner">
      <div className="summary-banner__title">
        <h2 className="summary-banner__heading">Your Plan: {programNames}</h2>
        <p className="summary-banner__sub">
          You've completed {result.completed_count} course{result.completed_count !== 1 ? 's' : ''}.
          Here's what's left.
        </p>
      </div>

      <div className="summary-stats">
        <div className="stat">
          <span className="stat__value">{directCourses.length}</span>
          <span className="stat__label">Courses needed</span>
        </div>
        <div className="stat stat--divider" />
        <div className="stat">
          <span className="stat__value">{result.total_additional_credits}</span>
          <span className="stat__label">Total credits</span>
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

      {result.unresolved_groups.length > 0 && (
        <div className="alert alert--warning">
          <strong>{result.unresolved_groups.length} open-ended requirement{result.unresolved_groups.length !== 1 ? 's' : ''}</strong> need manual selection
          (language requirement, L&S breadth, etc.). These are listed at the bottom.
        </div>
      )}
    </div>
  )
}
