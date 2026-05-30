import { useState, useRef } from 'react'

/**
 * PlannedScheduleImport
 *
 * Upload one or two DARS PDFs (IE and/or DS) to the backend parser and get
 * back a structured semester plan.
 *
 * Props:
 *   onImport(schedule)  — called with ParsedScheduleResponse on success
 *   onCancel()          — called when the user dismisses the panel
 */
export default function PlannedScheduleImport({ onImport, onCancel }) {
  const [files,   setFiles]   = useState([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const inputRef = useRef(null)

  function handleFileChange(e) {
    const selected = Array.from(e.target.files).filter(f => f.name.endsWith('.pdf'))
    setFiles(selected)
    setError(null)
  }

  async function handleParse() {
    if (files.length === 0) {
      setError('Please select at least one DARS PDF.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      for (const f of files) form.append('files', f)
      const res = await fetch('/api/parse-planned-schedule', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Server error ${res.status}`)
      }
      const schedule = await res.json()
      if (!schedule.semesters || schedule.semesters.length === 0) {
        throw new Error(
          'No planned courses found in the PDF(s). ' +
          'Make sure you are uploading a planned DARS — not a completed transcript.'
        )
      }
      onImport(schedule)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const totalFiles = files.length

  return (
    <div className="dars-import">
      <div className="dars-import__header">
        <h3 className="dars-import__title">📂 Import DARS Schedule</h3>
        <p className="dars-import__desc">
          Upload your planned DARS PDF(s) from MyUW. The app reads your future-semester
          courses and turns them into a ready-made degree plan. You can upload your IE
          DARS, DS DARS, or both — shared courses are automatically merged.
        </p>
      </div>

      {/* Drop / click zone */}
      <div
        className="dars-import__dropzone"
        onClick={() => inputRef.current?.click()}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Select DARS PDF files"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {totalFiles === 0 ? (
          <>
            <span className="dars-import__drop-icon">📄</span>
            <span className="dars-import__drop-label">Click to select DARS PDF(s)</span>
            <span className="dars-import__drop-hint">IE DARS, DS DARS, or both — up to 2 files</span>
          </>
        ) : (
          <ul className="dars-import__file-list">
            {files.map(f => (
              <li key={f.name} className="dars-import__file-item">
                📄 <strong>{f.name}</strong>
                <span className="dars-import__file-size">
                  &nbsp;({(f.size / 1024).toFixed(0)} KB)
                </span>
              </li>
            ))}
            <li className="dars-import__file-change">Click to change selection</li>
          </ul>
        )}
      </div>

      {error && (
        <div className="alert alert--error" style={{ marginTop: '10px' }}>
          {error}
        </div>
      )}

      <div className="dars-import__actions">
        <button className="btn btn--ghost" onClick={onCancel} disabled={loading}>
          Cancel
        </button>
        <button
          className="btn btn--primary"
          onClick={handleParse}
          disabled={loading || totalFiles === 0}
        >
          {loading
            ? <><span className="btn__spinner" /> Parsing…</>
            : 'Parse DARS →'
          }
        </button>
      </div>
    </div>
  )
}
