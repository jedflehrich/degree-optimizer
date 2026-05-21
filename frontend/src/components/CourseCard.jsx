/**
 * CourseCard
 * Displays a single recommended course with overlap, prereq, and credit badges.
 */
export default function CourseCard({ course, index }) {
  const isOverlap = course.overlap_score > 1
  const cantTakeNow = !course.can_take_now
  const isPrereq = course.is_prereq_filler

  return (
    <div className={`course-card ${isOverlap ? 'course-card--overlap' : ''} ${cantTakeNow ? 'course-card--blocked' : ''}`}>
      {/* Position indicator */}
      <span className="course-card__index">{index + 1}</span>

      {/* Main info */}
      <div className="course-card__body">
        <div className="course-card__top">
          <span className="course-card__id">{course.course_id.replace(/_/g, ' ')}</span>
          <div className="course-card__badges">
            <span className="badge badge--credits">{course.credits} cr</span>
            {isOverlap && (
              <span className="badge badge--overlap" title={`Counts toward ${course.overlap_score} programs`}>
                ✦ {course.overlap_score} programs
              </span>
            )}
            {isPrereq && (
              <span className="badge badge--prereq">Prereq</span>
            )}
            {cantTakeNow && (
              <span className="badge badge--blocked">Needs prereqs</span>
            )}
          </div>
        </div>
        <p className="course-card__name">{course.name}</p>
        {cantTakeNow && course.missing_prereqs.length > 0 && (
          <p className="course-card__prereq-warning">
            Must complete first:{' '}
            {course.missing_prereqs.map(p => p.replace(/_/g, ' ')).join(', ')}
          </p>
        )}
      </div>
    </div>
  )
}
