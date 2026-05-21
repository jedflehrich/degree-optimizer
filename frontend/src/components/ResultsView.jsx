import SummaryBanner from './SummaryBanner'
import CourseList from './CourseList'
import ProgramStatus from './ProgramStatus'

/**
 * ResultsView
 * The full results screen shown after the optimizer runs.
 * Layout: banner → two-column (course list | program status)
 */
export default function ResultsView({ result, onBack }) {
  return (
    <div className="results">
      {/* Back button */}
      <button className="btn btn--ghost results__back" onClick={onBack}>
        ← Edit inputs
      </button>

      {/* Summary stats */}
      <SummaryBanner result={result} />

      {/* Main content */}
      <div className="results__body">
        <div className="results__main">
          <CourseList courses={result.recommended_courses} />

          {/* Unresolved groups */}
          {result.unresolved_groups.length > 0 && (
            <section className="unresolved">
              <h3 className="unresolved__heading">Open-Ended Requirements</h3>
              <p className="unresolved__desc">
                These requirements couldn't be filled automatically — they need a
                specific course or advisor approval. Check with your advisor.
              </p>
              <ul className="unresolved__list">
                {result.unresolved_groups.map(g => (
                  <li key={g.group_id} className="unresolved__item">
                    <span className="unresolved__name">{g.group_name}</span>
                    {g.credits_still_needed > 0 && (
                      <span className="badge badge--gray">{g.credits_still_needed} cr needed</span>
                    )}
                    {g.courses_still_needed > 0 && (
                      <span className="badge badge--gray">{g.courses_still_needed} course(s) needed</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* Program status sidebar */}
        <aside className="results__sidebar">
          <ProgramStatus programStatuses={result.program_statuses} />
        </aside>
      </div>
    </div>
  )
}
