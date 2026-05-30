import { useState, useEffect, useRef } from 'react'

/**
 * APInput — fully controlled component.
 *
 * Props:
 *   apExams         — full list of AP exam objects from /api/ap-exams
 *   entries         — ApEntry[] controlled from parent (persisted in profile)
 *   onEntriesChange — called with the new full entries array on any change
 *
 * An ApEntry looks like:
 *   { examId, examName, score, description, courses: string[], genericCredit: string|null }
 */
export default function APInput({ apExams, apExamsLoading, apExamsError, onRetry, entries, onEntriesChange }) {
  const [query,        setQuery]        = useState('')
  const [filteredExams, setFilteredExams] = useState([])
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [selectedExam, setSelectedExam] = useState(null)
  const [score,        setScore]        = useState(4)
  const containerRef = useRef(null)

  // Filter exams as user types
  useEffect(() => {
    if (!query.trim()) {
      setFilteredExams(apExams)
    } else {
      const q = query.toLowerCase()
      setFilteredExams(apExams.filter(e =>
        e.exam.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q)
      ))
    }
  }, [query, apExams])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function selectExam(exam) {
    setSelectedExam(exam)
    setQuery(exam.exam)
    setDropdownOpen(false)
    setScore(4)
  }

  function getMatchingEntry(exam, score) {
    if (!exam) return null
    return exam.score_entries.find(e => e.scores.includes(score)) ?? null
  }

  function handleAdd() {
    if (!selectedExam) return
    const entry = getMatchingEntry(selectedExam, score)
    if (!entry) return

    const alreadyAdded = entries.some(a => a.examId === selectedExam.id && a.score === score)
    if (alreadyAdded) return

    const newEntry = {
      examId:        selectedExam.id,
      examName:      selectedExam.exam,
      score,
      description:   entry.description,
      courses:       entry.uw_courses,
      genericCredit: entry.generic_credit,
      credits:       entry.credits ?? 0,
    }
    onEntriesChange([...entries, newEntry])

    // Reset search
    setSelectedExam(null)
    setQuery('')
    setScore(4)
  }

  function removeEntry(index) {
    onEntriesChange(entries.filter((_, i) => i !== index))
  }

  const currentEntry = getMatchingEntry(selectedExam, score)

  // UW-Madison allows a maximum of 45 AP/transfer credit hours toward the degree.
  const AP_CREDIT_LIMIT = 45
  const totalApCredits = entries.reduce((sum, e) => sum + (e.credits || 0), 0)
  const isNearLimit = totalApCredits >= 40 && totalApCredits < AP_CREDIT_LIMIT
  const isAtLimit   = totalApCredits >= AP_CREDIT_LIMIT

  return (
    <div className="ap-input" ref={containerRef}>
      {/* Added AP credits */}
      {entries.length > 0 && (
        <div className="ap-entries">
          {entries.map((entry, i) => (
            <div key={i} className="ap-entry">
              <div className="ap-entry__info">
                <span className="ap-entry__name">AP {entry.examName}</span>
                <span className="badge badge--gray">Score {entry.score}</span>
                <span className="ap-entry__desc">→ {entry.description}</span>
                {entry.genericCredit && entry.courses.length === 0 && (
                  <span className="ap-entry__generic">(elective credit only)</span>
                )}
              </div>
              <button className="ap-entry__remove" onClick={() => removeEntry(i)} aria-label="Remove">×</button>
            </div>
          ))}

          {/* AP credit limit tracker */}
          <div className={`ap-credit-limit ${isAtLimit ? 'ap-credit-limit--over' : isNearLimit ? 'ap-credit-limit--near' : ''}`}>
            <span className="ap-credit-limit__label">AP credit total:</span>
            <span className="ap-credit-limit__count">{totalApCredits} / {AP_CREDIT_LIMIT} cr max</span>
            <button
              className="btn btn--ghost btn--sm clear-all-btn"
              onClick={() => onEntriesChange([])}
              title="Remove all AP credits"
            >
              Clear all
            </button>
            {isAtLimit && (
              <span className="ap-credit-limit__warning">
                ⚠ At UW-Madison's 45-credit AP/transfer limit — additional AP credits may not apply toward your degree.
              </span>
            )}
            {isNearLimit && (
              <span className="ap-credit-limit__warning">
                ℹ Close to UW-Madison's 45-credit AP/transfer limit.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Search + score row */}
      <div className="ap-input__row">
        <div className="ap-input__search-wrap">
          <input
            type="text"
            className="course-input__text"
            placeholder={apExamsLoading ? 'Loading AP exams…' : 'Search AP exam (e.g. Calculus BC, Statistics…)'}
            value={query}
            disabled={apExamsLoading || apExamsError}
            onChange={e => { setQuery(e.target.value); setSelectedExam(null); setDropdownOpen(true) }}
            onFocus={() => setDropdownOpen(true)}
          />
          {dropdownOpen && (
            <ul className="course-dropdown ap-dropdown">
              {filteredExams.length === 0 ? (
                <li className="course-dropdown__empty">No exams found</li>
              ) : (
                filteredExams.map(exam => (
                  <li key={exam.id} className="course-dropdown__item" onMouseDown={() => selectExam(exam)}>
                    <span className="course-dropdown__id">{exam.exam}</span>
                    <span className="course-dropdown__name">{exam.category}</span>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>

        <div className="ap-input__score-wrap">
          <label className="ap-input__score-label">Score</label>
          <select
            className="ap-input__score-select"
            value={score}
            onChange={e => setScore(Number(e.target.value))}
            disabled={!selectedExam}
          >
            {[3, 4, 5].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <button
          className="btn btn--primary"
          onClick={handleAdd}
          disabled={!selectedExam || !currentEntry}
        >
          Add
        </button>
      </div>

      {/* Preview */}
      {selectedExam && currentEntry && (
        <div className="ap-preview">
          <span className="ap-preview__label">Credit awarded:</span>
          <strong className="ap-preview__desc">{currentEntry.description}</strong>
          {currentEntry.uw_courses.length > 0 ? (
            <span className="ap-preview__courses">
              Course(s) added to completed list:{' '}
              {currentEntry.uw_courses.map(c => c.replace(/_/g, ' ')).join(', ')}
            </span>
          ) : (
            <span className="ap-preview__generic">
              General elective credit — won't directly satisfy a tracked requirement.
            </span>
          )}
          {selectedExam.notes && (
            <span className="ap-preview__note">⚠ {selectedExam.notes}</span>
          )}
        </div>
      )}

      {/* Loading / error states for the AP exam catalog */}
      {apExamsError && (
        <div className="ap-load-error">
          <span>Could not load AP exam list.</span>
          <button className="btn btn--sm" onClick={onRetry}>Retry</button>
        </div>
      )}

      {!apExamsError && entries.length === 0 && !selectedExam && (
        <p className="course-input__hint">
          {apExamsLoading
            ? 'Loading AP exam list…'
            : 'Search for an AP exam, select your score, and click Add. We\'ll automatically credit the equivalent UW-Madison course.'}
        </p>
      )}
    </div>
  )
}
