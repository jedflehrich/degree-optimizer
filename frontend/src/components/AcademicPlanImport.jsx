import { useState, useRef } from 'react'

/**
 * AcademicPlanImport
 *
 * Upload a UW-Madison Degree Plan ("BMD Plan") PDF exported from
 * Course Search & Enroll.  Calls POST /api/parse-academic-plan and
 * returns an AcademicPlanResponse.
 *
 * Props:
 *   onImport(plan)  — called with AcademicPlanResponse on success
 *   onCancel()      — called when the user dismisses the panel
 */
export default function AcademicPlanImport({ onImport, onCancel }) {
  const [file,    setFile]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const inputRef = useRef(null)

  function handleFileChange(e) {
    const f = e.target.files[0]
    if (f && f.name.endsWith('.pdf')) {
      setFile(f)
      setError(null)
    }
  }

  async function handleParse() {
    if (!file) {
      setError('Please select your Academic Plan PDF.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/parse-academic-plan', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Server error ${res.status}`)
      }
      const plan = await res.json()
      if (!plan.planned_semesters || plan.planned_semesters.length === 0) {
        throw new Error(
          'No upcoming courses found in the PDF. ' +
          'Make sure you are uploading a UW-Madison Degree Plan (BMD Plan) — ' +
          'not a transcript or DARS.'
        )
      }
      onImport(plan)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dars-import">
      <div className="dars-import__header">
        <h3 className="dars-import__title">📋 Import Academic Plan</h3>
        <p className="dars-import__desc">
          Upload your UW-Madison Degree Plan PDF (exported from Course Search &amp; Enroll
          → "BMD Plan"). The app reads your in-progress and planned semesters and
          pre-fills your selections automatically.
        </p>
      </div>

      {/* Drop / click zone */}
      <div
        className="dars-import__dropzone"
        onClick={() => inputRef.current?.click()}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Select Academic Plan PDF"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {!file ? (
          <>
            <span className="dars-import__drop-icon">📋</span>
            <span className="dars-import__drop-label">Click to select your Degree Plan PDF</span>
            <span className="dars-import__drop-hint">UW-Madison Degree Plan (BMD Plan) — single file</span>
          </>
        ) : (
          <ul className="dars-import__file-list">
            <li className="dars-import__file-item">
              📋 <strong>{file.name}</strong>
              <span className="dars-import__file-size">
                &nbsp;({(file.size / 1024).toFixed(0)} KB)
              </span>
            </li>
            <li className="dars-import__file-change">Click to change file</li>
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
          disabled={loading || !file}
        >
          {loading
            ? <><span className="btn__spinner" /> Parsing…</>
            : 'Parse Academic Plan →'
          }
        </button>
      </div>
    </div>
  )
}
