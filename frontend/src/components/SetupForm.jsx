import ProgramPicker from './ProgramPicker'
import CourseInput from './CourseInput'

/**
 * SetupForm
 * The landing screen: pick programs, enter completed courses, submit.
 */
export default function SetupForm({
  programs,
  selectedPrograms,
  onProgramsChange,
  completedCourses,
  onCoursesChange,
  onSubmit,
  loading,
  error,
}) {
  const canSubmit = selectedPrograms.length > 0 && !loading

  return (
    <div className="setup">
      <header className="setup__header">
        <h1 className="setup__title">
          <span className="setup__title-accent">Degree</span> Optimizer
        </h1>
        <p className="setup__subtitle">
          Find the shortest path to your UW‑Madison degree — with course overlaps maximized.
        </p>
      </header>

      <div className="setup__body">
        {/* Step 1 */}
        <section className="setup-section">
          <div className="setup-section__label">
            <span className="setup-section__num">1</span>
            <div>
              <h2 className="setup-section__title">Choose your programs</h2>
              <p className="setup-section__desc">Select every degree or major you want to complete simultaneously.</p>
            </div>
          </div>
          <ProgramPicker
            programs={programs}
            selected={selectedPrograms}
            onChange={onProgramsChange}
          />
        </section>

        {/* Step 2 */}
        <section className="setup-section">
          <div className="setup-section__label">
            <span className="setup-section__num">2</span>
            <div>
              <h2 className="setup-section__title">Enter completed courses</h2>
              <p className="setup-section__desc">Search and add every course you've already taken or transferred in.</p>
            </div>
          </div>
          <CourseInput value={completedCourses} onChange={onCoursesChange} />
        </section>

        {/* Error */}
        {error && (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          className="btn btn--primary btn--lg"
          onClick={onSubmit}
          disabled={!canSubmit}
        >
          {loading ? (
            <>
              <span className="btn__spinner" aria-hidden="true" />
              Generating plan…
            </>
          ) : (
            'Generate My Plan →'
          )}
        </button>

        {selectedPrograms.length === 0 && (
          <p className="setup__hint">Select at least one program to continue.</p>
        )}
      </div>
    </div>
  )
}
