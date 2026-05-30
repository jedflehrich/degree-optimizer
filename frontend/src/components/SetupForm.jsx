import ProgramPicker from './ProgramPicker'
import APInput from './APInput'
import CourseInput from './CourseInput'
import { timeAgo } from '../hooks/useProfile'

/**
 * SetupForm
 * Profile banner + three-step setup:
 *   1. Choose programs
 *   2. AP credits
 *   3. Other completed courses
 */
export default function SetupForm({
  // Profile
  name, onNameChange, savedAt, isReturning, onClear,
  // Programs
  programs, selectedPrograms, onProgramsChange,
  // AP
  apExams, apExamsLoading, apExamsError, onRetryApExams,
  apEntries, onApEntriesChange,
  // Manual courses
  manualCourses, onManualCoursesChange,
  // Submit
  onSubmit, loading, error,
}) {
  const canSubmit = selectedPrograms.length > 0 && !loading

  return (
    <div className="setup">
      {/* ── Profile Banner ──────────────────────────────────── */}
      <div className="profile-banner">
        <div className="profile-banner__left">
          {isReturning ? (
            <>
              <span className="profile-banner__greeting">
                👋 Welcome back{name ? `, ${name}` : ''}!
              </span>
              <span className="profile-banner__saved">
                Your courses and selections were restored.
                {savedAt && ` Last saved ${timeAgo(savedAt)}.`}
              </span>
            </>
          ) : (
            <>
              <span className="profile-banner__greeting">Create your student profile</span>
              <span className="profile-banner__saved">
                Your progress saves automatically — no account needed.
              </span>
            </>
          )}
        </div>

        <div className="profile-banner__right">
          <input
            type="text"
            className="profile-banner__name-input"
            placeholder="Your name (optional)"
            value={name}
            onChange={e => onNameChange(e.target.value)}
            maxLength={40}
          />
          {isReturning && (
            <button className="profile-banner__clear" onClick={onClear}>
              Clear & start over
            </button>
          )}
        </div>
      </div>

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
              <h2 className="setup-section__title">Enter AP credits</h2>
              <p className="setup-section__desc">
                We'll find the UW-Madison equivalent automatically.
              </p>
            </div>
          </div>
          <APInput
            apExams={apExams}
            apExamsLoading={apExamsLoading}
            apExamsError={apExamsError}
            onRetry={onRetryApExams}
            entries={apEntries}
            onEntriesChange={onApEntriesChange}
          />
        </section>

        {/* Step 3 */}
        <section className="setup-section">
          <div className="setup-section__label">
            <span className="setup-section__num">3</span>
            <div>
              <h2 className="setup-section__title">Other completed courses</h2>
              <p className="setup-section__desc">
                Add UW-Madison courses you've taken (transfers, dual enrollment, etc.).
                AP courses above are already included.
              </p>
            </div>
          </div>
          <CourseInput value={manualCourses} onChange={onManualCoursesChange} />
        </section>

        {error && (
          <div className="alert alert--error" role="alert">{error}</div>
        )}

        <button
          className="btn btn--primary btn--lg"
          onClick={onSubmit}
          disabled={!canSubmit}
        >
          {loading ? (
            <><span className="btn__spinner" aria-hidden="true" />Generating plan…</>
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
