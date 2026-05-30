import { useState, useEffect, useRef } from 'react'

/**
 * ProgramPicker
 * Multi-select dropdown for choosing degree programs.
 * Opens a panel with checkboxes; selected programs appear as dismissible chips.
 */
export default function ProgramPicker({ programs, selected, onChange }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  function toggle(id) {
    if (selected.includes(id)) {
      onChange(selected.filter(s => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  // Close dropdown when clicking outside the component.
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  if (!programs.length) {
    return <p className="picker-loading">Loading programs…</p>
  }

  const triggerLabel =
    selected.length === 0
      ? 'Select programs…'
      : selected.length === 1
        ? programs.find(p => p.program_id === selected[0])?.name ?? '1 program selected'
        : `${selected.length} programs selected`

  return (
    <div className="program-picker-dropdown" ref={containerRef}>
      {/* Trigger button */}
      <button
        type="button"
        className={`program-picker-dropdown__trigger ${open ? 'program-picker-dropdown__trigger--open' : ''}`}
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="program-picker-dropdown__label">{triggerLabel}</span>
        <span className="program-picker-dropdown__chevron" aria-hidden="true">
          {open ? '▲' : '▼'}
        </span>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="program-picker-dropdown__panel" role="listbox" aria-multiselectable="true">
          {programs.map(p => {
            const checked = selected.includes(p.program_id)
            return (
              <label
                key={p.program_id}
                className={`program-picker-dropdown__option ${checked ? 'program-picker-dropdown__option--checked' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(p.program_id)}
                  className="program-picker-dropdown__checkbox"
                />
                <span className="program-picker-dropdown__option-body">
                  <span className="program-picker-dropdown__option-name">{p.name}</span>
                  <span className="program-picker-dropdown__option-meta">
                    <span className="badge badge--gray">{p.degree}</span>
                    <span className="program-picker-dropdown__option-year">{p.catalog_year}</span>
                  </span>
                </span>
              </label>
            )
          })}
        </div>
      )}

      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="program-picker-dropdown__chips">
          {selected.map(id => {
            const p = programs.find(prog => prog.program_id === id)
            if (!p) return null
            return (
              <span key={id} className="program-chip">
                <span className="program-chip__name">{p.name}</span>
                <span className="badge badge--gray program-chip__badge">{p.degree}</span>
                <button
                  type="button"
                  className="program-chip__remove"
                  onClick={() => toggle(id)}
                  aria-label={`Remove ${p.name}`}
                >
                  ×
                </button>
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}
