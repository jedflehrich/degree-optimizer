import { useState } from 'react'
import CourseCard from './CourseCard'

/**
 * CourseList
 * Shows recommended courses in topological order.
 * Prereq-filler courses are collapsed by default (they clutter the main view).
 */
export default function CourseList({ courses }) {
  const [showPrereqs, setShowPrereqs] = useState(false)

  const direct = courses.filter(c => !c.is_prereq_filler)
  const prereqs = courses.filter(c => c.is_prereq_filler)

  return (
    <section className="course-list">
      <h3 className="course-list__heading">
        Courses to Take
        <span className="course-list__count">{direct.length} courses</span>
      </h3>
      <p className="course-list__desc">
        Listed in prerequisite order — take courses near the top first.
        <span className="badge badge--overlap" style={{ marginLeft: 8 }}>✦ Gold</span> = counts toward multiple programs.
      </p>

      <div className="course-list__items">
        {direct.map((course, i) => (
          <CourseCard key={course.course_id} course={course} index={i} />
        ))}
      </div>

      {prereqs.length > 0 && (
        <div className="prereq-section">
          <button
            className="prereq-section__toggle"
            onClick={() => setShowPrereqs(v => !v)}
          >
            {showPrereqs ? '▾' : '▸'} {prereqs.length} prerequisite filler course{prereqs.length !== 1 ? 's' : ''}
            <span className="prereq-section__hint">
              {showPrereqs ? 'hide' : 'show'} — these unlock other courses but don't directly satisfy a degree requirement
            </span>
          </button>
          {showPrereqs && (
            <div className="course-list__items course-list__items--prereqs">
              {prereqs.map((course, i) => (
                <CourseCard key={course.course_id} course={course} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
