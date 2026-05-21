import { useState, useEffect, useRef } from 'react'
import { searchCourses } from '../api'

/**
 * CourseInput
 * Debounced typeahead that searches /api/courses, shows a dropdown,
 * and lets the user build a chip list of completed course IDs.
 */
export default function CourseInput({ value, onChange }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const containerRef = useRef(null)

  // Debounced search
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        const data = await searchCourses(query.trim())
        // Filter out courses already added
        setResults(data.filter(c => !value.includes(c.id)))
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, value])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function addCourse(course) {
    onChange([...value, course.id])
    setQuery('')
    setResults([])
    setOpen(false)
  }

  function removeCourse(id) {
    onChange(value.filter(v => v !== id))
  }

  return (
    <div className="course-input" ref={containerRef}>
      {/* Chip list */}
      {value.length > 0 && (
        <div className="chip-list">
          {value.map(id => (
            <span key={id} className="chip">
              {id.replace(/_/g, ' ')}
              <button
                className="chip__remove"
                onClick={() => removeCourse(id)}
                aria-label={`Remove ${id}`}
              >×</button>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      <div className="course-input__field">
        <input
          type="text"
          className="course-input__text"
          placeholder="Search by course name or ID (e.g. STAT 240, Linear Algebra…)"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && <span className="course-input__spinner" aria-hidden="true" />}
      </div>

      {/* Dropdown */}
      {open && (
        <ul className="course-dropdown" role="listbox">
          {results.length === 0 ? (
            <li className="course-dropdown__empty">No courses found</li>
          ) : (
            results.slice(0, 12).map(course => (
              <li
                key={course.id}
                className="course-dropdown__item"
                role="option"
                onMouseDown={() => addCourse(course)}
              >
                <span className="course-dropdown__id">{course.id.replace(/_/g, ' ')}</span>
                <span className="course-dropdown__name">{course.name}</span>
                <span className="badge badge--gray">{course.credits} cr</span>
              </li>
            ))
          )}
        </ul>
      )}

      {value.length === 0 && (
        <p className="course-input__hint">
          Type at least 2 characters to search. Leave empty if you're starting fresh.
        </p>
      )}
    </div>
  )
}
