import { useState, useMemo } from 'react'
import { scheduleCourses, upcomingSemesters } from '../utils/semesterScheduler'

/**
 * SemesterPlanView
 *
 * Three display modes:
 *   'auto'  — optimizer auto-schedules selected courses into semesters
 *   'dars'  — shows your exact DARS-imported semester plan (FA26 → SP29)
 *   'plan'  — shows your Academic Plan (BMD Plan) semester-by-semester
 *
 * Props:
 *   courses          — final ordered CourseRecommendation[] from RequirementsPanel
 *   importedSchedule — ParsedScheduleResponse from DARS import (optional)
 *   academicPlanData — AcademicPlanResponse from Academic Plan import (optional)
 *   onBack           — go back to requirements panel
 */
export default function SemesterPlanView({ courses, importedSchedule = null, academicPlanData = null, onBack }) {
  const semesterOptions = useMemo(() => upcomingSemesters(8), [])
  const [startKey,    setStartKey]    = useState(semesterOptions[0].key)
  const [maxCredits,  setMaxCredits]  = useState(16)
  // Default to the most-detailed imported view if available
  const [mode,        setMode]        = useState(
    academicPlanData ? 'plan' : importedSchedule ? 'dars' : 'auto'
  )

  const autoPlan = useMemo(() => {
    const { type, year } = semesterOptions.find(s => s.key === startKey) ?? semesterOptions[0]
    return scheduleCourses(courses, type, year, maxCredits)
  }, [courses, startKey, maxCredits, semesterOptions])

  const totalCourses = courses.filter(c => !c.is_prereq_filler).length
  const totalCredits = courses.reduce((sum, c) => sum + c.credits, 0)

  // ── DARS mode stats ──────────────────────────────────────────────────────
  const darsSemesters    = importedSchedule?.semesters ?? []
  const darsTotalCredits = darsSemesters.reduce(
    (sum, sem) => sum + sem.courses.reduce((s, c) => s + c.credits, 0), 0
  )
  const darsTotalCourses = darsSemesters.reduce((sum, sem) => sum + sem.courses.length, 0)

  // ── Academic Plan mode stats ─────────────────────────────────────────────
  const planSemesters    = academicPlanData?.planned_semesters ?? []
  const planTotalCredits = planSemesters.reduce(
    (sum, sem) => sum + sem.courses.reduce((s, c) => s + c.credits, 0), 0
  )
  const planTotalCourses = planSemesters.reduce((sum, sem) => sum + sem.courses.length, 0)

  const showModeToggle = importedSchedule != null || academicPlanData != null

  return (
    <div className="sem-plan">
      {/* GPA / graduation requirements banner */}
      <div className="sem-plan__gpa-banner">
        <span className="sem-plan__gpa-icon">⚠️</span>
        <span>
          Graduation requires a <strong>minimum 2.000 cumulative GPA</strong> across at least
          120 credits. Your academic advisor can confirm your standing — this tool tracks
          courses, not grades.
        </span>
      </div>

      {/* Header */}
      <div className="sem-plan__topbar">
        <button className="btn btn--ghost" onClick={onBack}>← Back to Requirements</button>

        <div className="sem-plan__controls">
          {/* Mode toggle — only shown when DARS or Academic Plan is imported */}
          {showModeToggle && (
            <div className="sem-plan__mode-toggle">
              {academicPlanData && (
                <button
                  className={`sem-plan__mode-btn ${mode === 'plan' ? 'sem-plan__mode-btn--active' : ''}`}
                  onClick={() => setMode('plan')}
                >
                  📋 Your Academic Plan
                </button>
              )}
              {importedSchedule && (
                <button
                  className={`sem-plan__mode-btn ${mode === 'dars' ? 'sem-plan__mode-btn--active' : ''}`}
                  onClick={() => setMode('dars')}
                >
                  📂 Your DARS Plan
                </button>
              )}
              <button
                className={`sem-plan__mode-btn ${mode === 'auto' ? 'sem-plan__mode-btn--active' : ''}`}
                onClick={() => setMode('auto')}
              >
                ⚙ Auto-Schedule
              </button>
            </div>
          )}

          {/* Auto-mode controls */}
          {mode === 'auto' && (
            <>
              <label className="sem-control">
                <span className="sem-control__label">Start semester</span>
                <select
                  className="sem-control__select"
                  value={startKey}
                  onChange={e => setStartKey(e.target.value)}
                >
                  {semesterOptions.map(s => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </label>
              <label className="sem-control">
                <span className="sem-control__label">Max credits/semester</span>
                <select
                  className="sem-control__select"
                  value={maxCredits}
                  onChange={e => setMaxCredits(Number(e.target.value))}
                >
                  {[12, 13, 14, 15, 16, 17, 18].map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
            </>
          )}
        </div>
      </div>

      {/* ── Summary strip ─────────────────────────────────────────────────── */}
      {mode === 'auto' && (
        <div className="sem-plan__summary">
          <div className="sem-stat">
            <span className="sem-stat__val">{autoPlan.length}</span>
            <span className="sem-stat__lbl">Semesters</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{totalCourses}</span>
            <span className="sem-stat__lbl">Courses</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{totalCredits}</span>
            <span className="sem-stat__lbl">Total credits</span>
          </div>
          <p className="sem-plan__advisor-note">
            📋 This plan is a starting point. Always review with your academic advisor — they can
            account for retakes, waitlists, and requirements we may have missed.
          </p>
        </div>
      )}
      {mode === 'dars' && (
        <div className="sem-plan__summary">
          <div className="sem-stat">
            <span className="sem-stat__val">{darsSemesters.length}</span>
            <span className="sem-stat__lbl">Semesters</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{darsTotalCourses}</span>
            <span className="sem-stat__lbl">Courses</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{darsTotalCredits}</span>
            <span className="sem-stat__lbl">Credits planned</span>
          </div>
          <p className="sem-plan__advisor-note">
            📋 Imported from your DARS. Courses shown exactly as planned — including your
            current semester. Always confirm with your academic advisor.
          </p>
        </div>
      )}
      {mode === 'plan' && (
        <div className="sem-plan__summary">
          <div className="sem-stat">
            <span className="sem-stat__val">{planSemesters.length}</span>
            <span className="sem-stat__lbl">Semesters</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{planTotalCourses}</span>
            <span className="sem-stat__lbl">Courses</span>
          </div>
          <div className="sem-stat sem-stat--div" />
          <div className="sem-stat">
            <span className="sem-stat__val">{planTotalCredits}</span>
            <span className="sem-stat__lbl">Credits ahead</span>
          </div>
          <p className="sem-plan__advisor-note">
            📋 Imported from your UW-Madison Degree Plan. Shows your current and planned semesters
            as of your last save. Always confirm with your academic advisor.
          </p>
        </div>
      )}

      {/* ── Semester grid ─────────────────────────────────────────────────── */}
      {mode === 'auto' && (
        <div className="sem-grid">
          {autoPlan.map((sem, i) => (
            <SemesterColumn key={i} semester={sem} semNumber={i + 1} />
          ))}
        </div>
      )}
      {mode === 'dars' && (
        <div className="sem-grid">
          {darsSemesters.map((sem, i) => (
            <DARSSemesterColumn key={i} semester={sem} />
          ))}
        </div>
      )}
      {mode === 'plan' && (
        <div className="sem-grid">
          {planSemesters.map((sem, i) => (
            <AcPlanSemesterColumn key={i} semester={sem} />
          ))}
        </div>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   SemesterColumn — auto-plan mode
   -------------------------------------------------------------------------- */

function SemesterColumn({ semester, semNumber }) {
  const direct  = semester.courses.filter(c => !c.is_prereq_filler)
  const prereqs = semester.courses.filter(c => c.is_prereq_filler)
  const isHeavy = semester.credits > 17
  const isLight = semester.credits < 12

  return (
    <div className={`sem-col ${isHeavy ? 'sem-col--heavy' : ''}`}>
      <div className="sem-col__header">
        <span className="sem-col__name">{semester.name}</span>
        <span className={`sem-col__credits ${isHeavy ? 'sem-col__credits--heavy' : ''} ${isLight ? 'sem-col__credits--light' : ''}`}>
          {semester.credits} cr
        </span>
      </div>

      <div className="sem-col__courses">
        {direct.map(course => (
          <SemCourseCard key={course.course_id} course={course} />
        ))}
        {prereqs.map(course => (
          <SemCourseCard key={course.course_id} course={course} isPrereq />
        ))}
      </div>

      {isHeavy && (
        <p className="sem-col__warning">⚠ Heavy semester — consider spreading courses out</p>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   DARSSemesterColumn — DARS import mode
   -------------------------------------------------------------------------- */

function DARSSemesterColumn({ semester }) {
  const semCredits = semester.courses.reduce((sum, c) => sum + c.credits, 0)
  const isINP = semester.status === 'INP'
  const isHeavy = semCredits > 17
  const isLight = semCredits < 12

  return (
    <div className={`sem-col ${isINP ? 'sem-col--inp' : ''} ${isHeavy ? 'sem-col--heavy' : ''}`}>
      <div className="sem-col__header">
        <span className="sem-col__name">
          {semester.label}
          {isINP && <span className="sem-col__inp-badge">In Progress</span>}
        </span>
        <span className={`sem-col__credits ${isHeavy ? 'sem-col__credits--heavy' : ''} ${isLight ? 'sem-col__credits--light' : ''}`}>
          {semCredits} cr
        </span>
      </div>

      <div className="sem-col__courses">
        {semester.courses.map(course => (
          <DARSCourseCard key={course.course_id} course={course} />
        ))}
      </div>
    </div>
  )
}


/* --------------------------------------------------------------------------
   SemCourseCard — compact card for auto-plan mode
   -------------------------------------------------------------------------- */

function SemCourseCard({ course, isPrereq }) {
  const isOverlap = course.overlap_score > 1
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={[
        'sem-course',
        isOverlap  ? 'sem-course--overlap' : '',
        isPrereq   ? 'sem-course--prereq'  : '',
      ].join(' ')}
    >
      <div className="sem-course__top" onClick={() => setExpanded(v => !v)}>
        <span className="sem-course__id">{course.course_id.replace(/_/g, ' ')}</span>
        <div className="sem-course__badges">
          <span className="badge badge--credits">{course.credits} cr</span>
          {isOverlap && <span className="badge badge--overlap">✦</span>}
          {isPrereq  && <span className="badge badge--prereq">Prereq</span>}
        </div>
      </div>
      {expanded && (
        <div className="sem-course__detail">
          <p className="sem-course__name">{course.name}</p>
          {course.satisfies_groups.length > 0 && (
            <p className="sem-course__satisfies">
              Fulfills: {course.satisfies_groups.join(', ')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   DARSCourseCard — compact card for DARS import mode
   -------------------------------------------------------------------------- */

function DARSCourseCard({ course }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="sem-course sem-course--dars">
      <div className="sem-course__top" onClick={() => setExpanded(v => !v)}>
        <span className="sem-course__id">{course.course_id.replace(/_/g, ' ')}</span>
        <div className="sem-course__badges">
          <span className="badge badge--credits">{course.credits} cr</span>
        </div>
      </div>
      {expanded && (
        <div className="sem-course__detail">
          <p className="sem-course__name">{course.name}</p>
        </div>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   AcPlanSemesterColumn — Academic Plan mode (status: completed/in_progress/planned)
   -------------------------------------------------------------------------- */

function AcPlanSemesterColumn({ semester }) {
  const semCredits = semester.courses.reduce((sum, c) => sum + c.credits, 0)
  const isINP   = semester.status === 'in_progress'
  const isHeavy = semCredits > 17
  const isLight = semCredits < 12

  return (
    <div className={`sem-col ${isINP ? 'sem-col--inp' : ''} ${isHeavy ? 'sem-col--heavy' : ''}`}>
      <div className="sem-col__header">
        <span className="sem-col__name">
          {semester.label}
          {isINP && <span className="sem-col__inp-badge">In Progress</span>}
        </span>
        <span className={`sem-col__credits ${isHeavy ? 'sem-col__credits--heavy' : ''} ${isLight ? 'sem-col__credits--light' : ''}`}>
          {semCredits} cr
        </span>
      </div>

      <div className="sem-col__courses">
        {semester.courses.map(course => (
          <AcPlanCourseCard key={course.course_id} course={course} />
        ))}
      </div>
    </div>
  )
}


/* --------------------------------------------------------------------------
   AcPlanCourseCard — compact card for Academic Plan mode
   -------------------------------------------------------------------------- */

function AcPlanCourseCard({ course }) {
  const [expanded, setExpanded] = useState(false)
  const isIP = course.grade === 'IP'

  return (
    <div className={`sem-course sem-course--dars ${isIP ? 'sem-course--inp' : ''}`}>
      <div className="sem-course__top" onClick={() => setExpanded(v => !v)}>
        <span className="sem-course__id">{course.course_id.replace(/_/g, ' ')}</span>
        <div className="sem-course__badges">
          <span className="badge badge--credits">{course.credits} cr</span>
          {isIP && <span className="badge badge--inp">In Progress</span>}
        </div>
      </div>
      {expanded && course.name && (
        <div className="sem-course__detail">
          <p className="sem-course__name">{course.name}</p>
        </div>
      )}
    </div>
  )
}
