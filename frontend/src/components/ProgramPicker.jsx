/**
 * ProgramPicker
 * Renders a checkbox card for each available program.
 * At least one must be selected before the user can submit.
 */
export default function ProgramPicker({ programs, selected, onChange }) {
  function toggle(id) {
    if (selected.includes(id)) {
      onChange(selected.filter(s => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  if (!programs.length) {
    return <p className="picker-loading">Loading programs…</p>
  }

  return (
    <div className="program-picker">
      {programs.map(p => {
        const checked = selected.includes(p.program_id)
        return (
          <label key={p.program_id} className={`program-card ${checked ? 'program-card--checked' : ''}`}>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(p.program_id)}
            />
            <span className="program-card__body">
              <span className="program-card__name">{p.name}</span>
              <span className="program-card__meta">
                <span className="badge badge--gray">{p.degree}</span>
                <span className="program-card__year">{p.catalog_year}</span>
              </span>
            </span>
          </label>
        )
      })}
    </div>
  )
}
