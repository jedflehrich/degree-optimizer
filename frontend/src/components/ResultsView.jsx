import { useState } from 'react'
import SummaryBanner from './SummaryBanner'
import RequirementsPanel from './RequirementsPanel'
import SemesterPlanView from './SemesterPlanView'
import ProgramStatus from './ProgramStatus'
import PlannedScheduleImport from './PlannedScheduleImport'
import AcademicPlanImport from './AcademicPlanImport'

/**
 * ResultsView
 * Manages two sub-views:
 *   'requirements' — requirements-organized panel with course selection
 *   'semester'     — semester-by-semester plan
 *
 * Both sub-views are kept mounted (display:none when not active) so that
 * selections made in RequirementsPanel are preserved when navigating to
 * the semester plan and back.
 */
export default function ResultsView({ result, catalog = [], onBack, onReoptimize, onSelectionIdsChange, loadedCourseIds = null }) {
  const [subView, setSubView]           = useState('requirements')
  const [finalCourses, setFinalCourses] = useState([])
  // plannedCourses: courses the user has selected in the requirements panel
  // (used to show a light-green "planned" segment in the progress bar)
  const [plannedCourses, setPlannedCourses] = useState([])

  // DARS import state
  const [showImport,       setShowImport]       = useState(false)
  const [importedSchedule, setImportedSchedule] = useState(null)

  // Academic Plan import state
  const [showPlanImport,    setShowPlanImport]    = useState(false)
  const [academicPlanData,  setAcademicPlanData]  = useState(null)

  // Focus area (and any other one_of) choices: groupId → chosen sub-group id
  const [oneOfChoices,   setOneOfChoices]   = useState({})
  const [isReoptimizing, setIsReoptimizing] = useState(false)

  function handleConfirmRequirements(courses) {
    setFinalCourses(courses)
    setSubView('semester')
  }

  // Called by RequirementsPanel whenever selections change.
  // Keeps the progress bar updated AND reports IDs up to App.jsx for saving.
  function handleSelectionsChange(courses) {
    setPlannedCourses(courses)
    onSelectionIdsChange?.(courses.map(c => c.course_id))
  }

  function handleImport(schedule) {
    setImportedSchedule(schedule)
    setShowImport(false)
    // Pre-populate the progress bar's planned segment with all DARS courses
    // that appear in the optimizer result.
    const darsIds = new Set(schedule.all_course_ids)
    const darsPlanned = result.recommended_courses.filter(c => darsIds.has(c.course_id))
    setPlannedCourses(darsPlanned)
  }

  function handleAcademicPlanImport(plan) {
    setAcademicPlanData(plan)
    setShowPlanImport(false)
    // Pre-populate the progress bar with all planned (non-completed) courses
    // from the Academic Plan that appear in the optimizer result.
    const planIds = new Set(plan.all_planned_course_ids)
    const planPlanned = result.recommended_courses.filter(c => planIds.has(c.course_id))
    setPlannedCourses(planPlanned)
  }

  /**
   * Called when the student picks a focus area (or any one_of group choice).
   * Re-runs the optimizer with the chosen sub-group locked in.
   */
  async function handlePickOneOf(groupId, subGroupId) {
    if (!onReoptimize) return
    const newChoices = { ...oneOfChoices, [groupId]: subGroupId }
    setOneOfChoices(newChoices)
    setIsReoptimizing(true)
    try {
      await onReoptimize({ one_of_overrides: newChoices })
    } finally {
      setIsReoptimizing(false)
    }
  }

  // Detect IE + DS double major so we can surface the L&S waiver note.
  const hasIEandDS =
    result.target_program_ids.includes('uw-madison-ie-bs-2025') &&
    result.target_program_ids.includes('uw-madison-ds-bs-2025')

  return (
    <div className="results">
      {/* Top bar: back button + import toggles (only in requirements view) */}
      {subView === 'requirements' && (
        <div className="results__topbar">
          <button className="btn btn--ghost results__back" onClick={onBack}>
            ← Edit inputs
          </button>
          <div className="results__import-group">
            <button
              className={`btn btn--ghost results__import-btn ${importedSchedule ? 'results__import-btn--active' : ''}`}
              onClick={() => { setShowImport(v => !v); setShowPlanImport(false) }}
            >
              {importedSchedule ? '✓ DARS imported' : '📂 Import DARS'}
            </button>
            <button
              className={`btn btn--ghost results__import-btn ${academicPlanData ? 'results__import-btn--active' : ''}`}
              onClick={() => { setShowPlanImport(v => !v); setShowImport(false) }}
            >
              {academicPlanData ? '✓ Plan imported' : '📋 Import Academic Plan'}
            </button>
          </div>
        </div>
      )}

      {/* DARS import panel */}
      {showImport && subView === 'requirements' && (
        <PlannedScheduleImport
          onImport={handleImport}
          onCancel={() => setShowImport(false)}
        />
      )}

      {/* Academic Plan import panel */}
      {showPlanImport && subView === 'requirements' && (
        <AcademicPlanImport
          onImport={handleAcademicPlanImport}
          onCancel={() => setShowPlanImport(false)}
        />
      )}

      {/* Summary banner always visible */}
      <SummaryBanner result={result} plannedCourses={plannedCourses} />

      {/* ── Requirements view ─────────────────────────────────────────────────
          Kept mounted (display:none when hidden) so selections are preserved
          when the student goes to the semester plan and comes back.          */}
      <div style={{ display: subView === 'requirements' ? '' : 'none' }}>
        {hasIEandDS && (
          <div className="alert alert--info" style={{ marginBottom: '1rem' }}>
            <strong>L&S requirements waived</strong> — As an IE + DS double major enrolled
            through the College of Engineering, the L&S breadth, language, and math
            distribution requirements are automatically waived. Only the DS major core
            and elective requirements apply. Those waived requirements are hidden below.
          </div>
        )}

        {isReoptimizing && (
          <div className="alert alert--info" style={{ marginBottom: '1rem' }}>
            ⏳ Recalculating recommendations for your chosen focus area…
          </div>
        )}

        <div className="results__body">
          <div className="results__main">
            <RequirementsPanel
              result={result}
              catalog={catalog}
              hasIEandDS={hasIEandDS}
              onConfirm={handleConfirmRequirements}
              onSelectionsChange={handleSelectionsChange}
              importedCourseIds={
                // Priority: Academic Plan > DARS import > saved plan selections
                academicPlanData?.all_planned_course_ids ??
                importedSchedule?.all_course_ids ??
                loadedCourseIds ??
                null
              }
              onPickOneOf={handlePickOneOf}
              oneOfChoices={oneOfChoices}
            />
          </div>
          <aside className="results__sidebar">
            <ProgramStatus
              programStatuses={result.program_statuses}
              plannedCourses={plannedCourses}
            />
          </aside>
        </div>
      </div>

      {/* ── Semester plan view ────────────────────────────────────────────────
          Also kept mounted so the plan isn't lost if the user goes back.    */}
      <div style={{ display: subView === 'semester' ? '' : 'none' }}>
        <SemesterPlanView
          courses={finalCourses}
          importedSchedule={importedSchedule}
          academicPlanData={academicPlanData}
          onBack={() => setSubView('requirements')}
        />
      </div>
    </div>
  )
}
