import React, { useState } from 'react'
import { localizeScheme } from './translations'

const CATEGORY_ICONS = {
  Farmers: '🌾',
  Students: '🎓',
  Women: '👩',
  'Small Business Owners': '🏪',
  'General Public': '🏥',
}

export function SchemeCard({ scheme, lang, labels, onClick, onCompareToggle, inCompare }) {
  const display = localizeScheme(scheme, lang)
  return (
    <button className={`scheme-card${inCompare ? ' scheme-card--comparing' : ''}`} onClick={() => onClick(scheme)}>
      <span className="scheme-icon" aria-hidden="true">{CATEGORY_ICONS[scheme.category] || '▤'}</span>
      <span className="category-tag">{display.category}</span>
      <strong>{scheme.name}</strong>
      <span className="card-description">{display.description}</span>
      <div className="card-footer">
        <span className="card-link">{labels.details} <span aria-hidden="true">↗</span></span>
        {onCompareToggle && (
          <button
            className={`compare-toggle${inCompare ? ' compare-toggle--active' : ''}`}
            aria-label={inCompare ? labels.removeFromCompare : labels.addToCompare}
            onClick={e => { e.stopPropagation(); onCompareToggle(scheme) }}
          >
            {inCompare ? '✓' : '+'}
          </button>
        )}
      </div>
    </button>
  )
}

export function SchemeDetails({ scheme, lang, labels, onClose }) {
  const [copied, setCopied] = useState(false)
  if (!scheme) return null
  const display = localizeScheme(scheme, lang)

  function copyDetails() {
    const text = [
      scheme.name,
      display.description,
      `${labels.eligibility}: ${display.eligibility?.join('; ')}`,
      `${labels.benefits}: ${display.benefits?.join('; ')}`,
      scheme.official_url,
    ].join('\n')
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <section className="scheme-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-header">
          <button className="modal-close" aria-label="Close" onClick={onClose}>&times;</button>
          <button className="modal-copy" aria-label={labels.copy} onClick={copyDetails} title={labels.copy}>
            {copied ? '✓' : '⎘'}
          </button>
        </div>
        <span className="category-tag">{display.category}</span>
        <h2 id="modal-title">{scheme.name}</h2>
        <p>{display.description}</p>
        <p><strong>{labels.who}:</strong> {display.beneficiaries}</p>
        <h3>{labels.benefits}</h3>
        <ul>{(display.benefits || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
        <h3>{labels.eligibility}</h3>
        <ul>{(display.eligibility || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
        {scheme.required_documents && scheme.required_documents.length > 0 && (
          <>
            <h3>{labels.requiredDocs || 'Documents Required'}</h3>
            <ul>{scheme.required_documents.map((doc, i) => <li key={i}>{doc}</li>)}</ul>
          </>
        )}
        <h3>{labels.process}</h3>
        <ol>{(display.application || []).map((item, i) => <li key={i}>{item}</li>)}</ol>
        <p className="verified-note">{labels.verified}: {scheme.last_verified}</p>
        <a className="primary-button source-button" href={scheme.official_url} target="_blank" rel="noreferrer">
          {labels.source}: {scheme.source_note} ↗
        </a>
      </section>
    </div>
  )
}

export function SchemeCompare({ schemes, lang, labels, onClose }) {
  if (!schemes || schemes.length < 2) return null
  const displays = schemes.map(s => localizeScheme(s, lang))
  const fields = [
    { key: 'description', label: labels.details },
    { key: 'benefits', label: labels.benefits, isList: true },
    { key: 'eligibility', label: labels.eligibility, isList: true },
    { key: 'required_documents', label: labels.requiredDocs || 'Documents Required', isList: true, fromScheme: true },
  ]
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <section className="compare-modal" role="dialog" aria-modal="true">
        <button className="modal-close" aria-label="Close" onClick={onClose}>&times;</button>
        <h2>{labels.compareSchemes || 'Compare Schemes'}</h2>
        <div className="compare-grid" style={{ gridTemplateColumns: `180px repeat(${schemes.length}, 1fr)` }}>
          {/* Header row */}
          <div className="compare-label-cell" />
          {displays.map((d, i) => (
            <div key={i} className="compare-scheme-name">
              <span className="scheme-icon">{CATEGORY_ICONS[schemes[i].category] || '▤'}</span>
              <span className="category-tag">{d.category}</span>
              <strong>{schemes[i].name}</strong>
            </div>
          ))}
          {/* Field rows */}
          {fields.map(({ key, label, isList, fromScheme }) => (
            <React.Fragment key={key}>
              <div className="compare-label-cell"><strong>{label}</strong></div>
              {displays.map((d, i) => {
                const val = fromScheme ? schemes[i][key] : d[key]
                return (
                  <div key={i} className="compare-value-cell">
                    {isList && Array.isArray(val)
                      ? <ul>{val.map((v, j) => <li key={j}>{v}</li>)}</ul>
                      : <p>{val || '—'}</p>}
                  </div>
                )
              })}
            </React.Fragment>
          ))}
          {/* Official URL row */}
          <div className="compare-label-cell"><strong>{labels.source}</strong></div>
          {schemes.map((s, i) => (
            <div key={i} className="compare-value-cell">
              <a href={s.official_url} target="_blank" rel="noreferrer">{s.source_note} ↗</a>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export function ErrorNotice({ error, onDismiss }) {
  if (!error) return null
  return (
    <div className="alert" role="alert">
      <span>{error}</span>
      {onDismiss && <button onClick={onDismiss}>Dismiss</button>}
    </div>
  )
}

export function LoadingState({ children = 'Loading…' }) {
  return <p className="status" role="status">{children}</p>
}
