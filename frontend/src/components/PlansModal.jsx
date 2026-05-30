/**
 * PlansModal — list and load saved degree plans.
 *
 * Props:
 *   plans        — array of plan summaries { id, name, target_program_ids, updated_at }
 *   loadingPlans — true while the list is being fetched
 *   onLoad(id)   — called when the user clicks "Load" on a plan
 *   onDelete(id) — called when the user clicks "Delete"
 *   onClose      — called to dismiss the modal
 */

export default function PlansModal({ plans, loadingPlans, onLoad, onDelete, onClose }) {

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  function formatDate(iso) {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  }

  function programLabel(ids) {
    if (!ids?.length) return 'No programs'
    return ids
      .map(id => {
        if (id.includes('ds-bs'))  return 'Data Science BS'
        if (id.includes('ie-bs'))  return 'Industrial Engineering BS'
        if (id.includes('cs-bs'))  return 'Computer Science BS'
        if (id.includes('econ'))   return 'Economics BS'
        if (id.includes('psych'))  return 'Psychology BS'
        if (id.includes('bio'))    return 'Biology BS'
        if (id.includes('math'))   return 'Math BS'
        return id
      })
      .join(' + ')
  }

  return (
    <div className="auth-overlay" onClick={handleOverlayClick}>
      <div className="plans-modal">

        <button className="auth-modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>

        <h2 className="auth-modal__title">Saved plans</h2>

        {loadingPlans ? (
          <p className="plans-modal__empty">Loading…</p>
        ) : plans.length === 0 ? (
          <p className="plans-modal__empty">
            No saved plans yet. Build a semester plan and click <strong>Save plan</strong> to save it here.
          </p>
        ) : (
          <ul className="plans-modal__list">
            {plans.map(plan => (
              <li key={plan.id} className="plans-modal__item">
                <div className="plans-modal__info">
                  <strong className="plans-modal__name">{plan.name}</strong>
                  <span className="plans-modal__programs">
                    {programLabel(plan.target_program_ids)}
                  </span>
                  <span className="plans-modal__date">
                    Saved {formatDate(plan.updated_at)}
                  </span>
                </div>
                <div className="plans-modal__actions">
                  <button
                    className="btn btn--primary"
                    onClick={() => { onLoad(plan.id); onClose() }}
                  >
                    Load
                  </button>
                  <button
                    className="btn btn--ghost"
                    onClick={() => onDelete(plan.id)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

      </div>
    </div>
  )
}
