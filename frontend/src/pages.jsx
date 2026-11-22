import React, { useEffect, useReducer, useRef, useState } from 'react'
import { postJson, request } from './api'
import { ErrorNotice, LoadingState, SchemeCard, SchemeCompare } from './components'
import { eligibilityReducer, initialEligibilityState, visibleEligibilityQuestions } from './eligibilityState.js'
import { eligibilityCopy } from './translations'

const categories = ['Farmers', 'Students', 'Women', 'Small Business Owners', 'General Public']

function CategoryName({ category, lang }) {
  const labels = {
    te: { Farmers: 'రైతులు', Students: 'విద్యార్థులు', Women: 'మహిళలు', 'Small Business Owners': 'చిన్న వ్యాపార యజమానులు', 'General Public': 'సాధారణ ప్రజలు' },
    hi: { Farmers: 'किसान', Students: 'विद्यार्थी', Women: 'महिलाएँ', 'Small Business Owners': 'छोटे व्यवसाय के मालिक', 'General Public': 'सामान्य नागरिक' },
  }
  return labels[lang]?.[category] || category
}

function CategoryFilter({ value, onChange, lang, label }) {
  return (
    <div className="filter-row">
      <label className="sr-only" htmlFor="category-filter">{label}</label>
      <select id="category-filter" value={value} onChange={e => onChange(e.target.value)}>
        <option value="">{label}</option>
        {categories.map(category => (
          <option value={category} key={category}><CategoryName category={category} lang={lang}/></option>
        ))}
      </select>
    </div>
  )
}

function SectionHeading({ eyebrow, title, intro, children }) {
  return (
    <div className="section-heading">
      <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{intro && <p>{intro}</p>}</div>
      {children}
    </div>
  )
}

// ── Voice input hook ──────────────────────────────────────────────────────────
function useVoiceInput(lang, onResult) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(() =>
    typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  )
  const recogRef = useRef(null)

  const langCodes = { en: 'en-IN', te: 'te-IN', hi: 'hi-IN' }

  function start() {
    if (!supported) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const recog = new SR()
    recog.lang = langCodes[lang] || 'en-IN'
    recog.interimResults = false
    recog.maxAlternatives = 1
    recog.onresult = e => {
      const transcript = e.results[0][0].transcript
      onResult(transcript)
      setListening(false)
    }
    recog.onerror = () => setListening(false)
    recog.onend = () => setListening(false)
    recogRef.current = recog
    recog.start()
    setListening(true)
  }

  function stop() {
    recogRef.current?.stop()
    setListening(false)
  }

  return { supported, listening, start, stop }
}

// ── TTS helper ───────────────────────────────────────────────────────────────
function speakText(text, lang) {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text.slice(0, 500))
  const langCodes = { en: 'en-IN', te: 'te-IN', hi: 'hi-IN' }
  utter.lang = langCodes[lang] || 'en-IN'
  window.speechSynthesis.speak(utter)
}

export function HomePage({ t, lang, navigate, onSelectScheme }) {
  const [query, setQuery] = useState('')
  const [featured, setFeatured] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    request('/schemes', {}, lang).then(data => { if (active) setFeatured(data.items.slice(0, 3)) })
      .catch(e => { if (active) setError(e.message || t.retry) })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [t.retry])
  function search(e) {
    e.preventDefault()
    navigate(`/schemes${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''}`)
  }
  return <>
    <section className="hero"><div className="hero-copy"><span className="eyebrow"><span className="sparkle">✳</span> {t.eyebrow}</span><h1>{t.title}</h1><p>{t.intro}</p>
      <form className="search-box" onSubmit={search}><span className="search-icon" aria-hidden="true">⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t.search} aria-label={t.search}/><button>{t.find}<span aria-hidden="true"> ↗</span></button></form>
      <span className="hero-note">{t.greeting}</span></div>
      <div className="hero-art" aria-hidden="true"><div className="sun-orbit orbit-one"/><div className="sun-orbit orbit-two"/><div className="sun-disc"/><div className="art-leaf leaf-a"/><div className="art-leaf leaf-b"/><div className="art-stem"/><div className="art-card"><span>भारत</span><b>सहायता<br/>आपके लिए</b><i>✳</i></div><div className="art-dot dot-a"/><div className="art-dot dot-b"/></div>
    </section>
    <section className="content-section home-featured"><SectionHeading eyebrow="FEATURED SCHEMES" title="Start with a few popular schemes" intro="Browse the full catalogue to search by name or category."/><div className="scheme-grid">
      {busy ? <LoadingState/> : error ? <ErrorNotice error={error}/> : featured.map(scheme => <SchemeCard key={scheme.id} scheme={scheme} lang={lang} labels={t} onClick={onSelectScheme}/>)}
    </div><a className="primary-button home-browse" href="/schemes" onClick={e => { e.preventDefault(); navigate('/schemes') }}>{t.all} <span>↗</span></a></section>
    <section className="quick-links"><SectionHeading eyebrow="YOJANAMITRA TOOLS" title="Choose what you need"/><div className="quick-link-grid">
      {[
        ['/schemes', t.all, 'Search and compare all listed government schemes.'],
        ['/eligibility', t.eligible, t.eligibleIntro],
        ['/assistant', t.assistant, 'Ask a question and get grounded scheme information.'],
        ['/documents', t.docs, 'Upload a PDF and get a plain-language summary.'],
      ].map(([href, title, body]) => <a className="quick-link-card" href={href} key={href} onClick={e => { e.preventDefault(); navigate(href) }}><span className="quick-link-arrow">↗</span><strong>{title}</strong><span>{body}</span></a>)}
    </div></section>
    <TrustStrip/>
  </>
}

export function SchemesPage({ t, lang, search, onSelectScheme }) {
  const initialQuery = new URLSearchParams(search).get('q') || ''
  const [query, setQuery] = useState(initialQuery)
  const [category, setCategory] = useState('')
  const [schemes, setSchemes] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [compareList, setCompareList] = useState([])
  const [showCompare, setShowCompare] = useState(false)

  async function load(q = query, cat = category) {
    setBusy(true); setError('')
    try {
      const params = new URLSearchParams()
      if (q.trim()) params.set('q', q.trim())
      if (cat) params.set('category', cat)
      setSchemes((await request(`/schemes?${params}`, {}, lang)).items)
    } catch (e) { setError(e.message || t.retry) }
    finally { setBusy(false) }
  }
  useEffect(() => { const q = new URLSearchParams(search).get('q') || ''; setQuery(q); load(q, category) }, [search])

  function toggleCompare(scheme) {
    setCompareList(prev => {
      const exists = prev.find(s => s.id === scheme.id)
      if (exists) return prev.filter(s => s.id !== scheme.id)
      if (prev.length >= 3) return prev
      return [...prev, scheme]
    })
  }

  return (
    <section className="page-section content-section">
      <SectionHeading eyebrow="01 / DISCOVER" title={t.schemes} intro="Explore the full YojanaMitra catalogue of government schemes.">
        <CategoryFilter value={category} label={t.categories} lang={lang} onChange={value => { setCategory(value); load(query, value) }}/>
      </SectionHeading>
      <form className="search-box schemes-search" onSubmit={e => { e.preventDefault(); load() }}>
        <span className="search-icon" aria-hidden="true">⌕</span>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder={t.search} aria-label={t.search}/>
        <button>{t.find}<span aria-hidden="true"> ↗</span></button>
      </form>
      <ErrorNotice error={error} onDismiss={() => setError('')}/>
      {busy ? <LoadingState/> : schemes.length === 0 ? <div className="empty-state">{t.noMatches}</div> :
        <div className="scheme-grid">
          {schemes.map(s => (
            <SchemeCard
              key={s.id} scheme={s} lang={lang} labels={t} onClick={onSelectScheme}
              onCompareToggle={toggleCompare}
              inCompare={!!compareList.find(c => c.id === s.id)}
            />
          ))}
        </div>
      }
      {compareList.length >= 2 && (
        <div className="compare-bar">
          <span>{t.comparing}: {compareList.map(s => s.name.split(' ').slice(0,2).join(' ')).join(', ')}</span>
          <button className="primary-button" onClick={() => setShowCompare(true)}>
            {t.compareSchemes || 'Compare'} ({compareList.length}) ↗
          </button>
          <button className="secondary-button" onClick={() => setCompareList([])}>✕</button>
        </div>
      )}
      {showCompare && (
        <SchemeCompare
          schemes={compareList} lang={lang} labels={t}
          onClose={() => setShowCompare(false)}
        />
      )}
    </section>
  )
}

export function EligibilityPage({ t, lang, navigate, onSelectScheme }) {
  const ui = eligibilityCopy[lang] || eligibilityCopy.en
  const [flow, dispatch] = useReducer(eligibilityReducer, initialEligibilityState)
  const { occupation, step, questions, answers, results } = flow
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function continueAssessment(event) {
    event.preventDefault(); setError('')
    if (step === 1) {
      setBusy(true)
      try {
        const response = await postJson('/eligibility', { occupation, phase: 'questions', step: 2 }, lang)
        dispatch({ type: 'QUESTIONS_LOADED', questions: response.questions })
      } catch (e) { setError(e.message || t.retry) }
      finally { setBusy(false) }
      return
    }
    if (step === 2) {
      setBusy(true)
      try {
        const response = await postJson('/eligibility', { occupation, phase: 'assess', answers }, lang)
        dispatch({ type: 'RESULTS_LOADED', results: response })
      } catch (e) { setError(e.message || t.retry) }
      finally { setBusy(false) }
    }
  }
  function changeProfile(nextOccupation) { dispatch({ type: 'PROFILE_CHANGED', occupation: nextOccupation }); setError('') }
  function checkAgain() { dispatch({ type: 'CHECK_AGAIN' }); setError('') }

  const resultGroups = results ? [
    ['likely_matches', ui.likely],
    ['needs_more_information', ui.more],
    ['unlikely_matches', ui.unlikely],
  ] : []
  const noResults = results && Object.values(results.counts).reduce((sum, count) => sum + count, 0) === 0
  const visibleQuestions = visibleEligibilityQuestions(occupation, questions, answers, step)

  return (
    <section className="page-section content-section"><div className="feature-page-panel eligibility-panel panel">
      <div className="panel-heading"><span className="feature-icon">03</span><span className="eyebrow">02 / PERSONALISE</span><h2>{t.eligible}</h2><p>{t.eligibleIntro}</p></div>
      <div className="assessment-progress" aria-label={`Step ${step} of 3`}><span>Step {step} of 3</span><div><i style={{width: `${step / 3 * 100}%`}}/></div></div>

      {step === 1 && <form className="assessment-form" onSubmit={continueAssessment}>
        <label className="profile-select"><span>{ui.profilePrompt}</span><select required value={occupation} onChange={event => changeProfile(event.target.value)}><option value="">{t.choose}</option><option value="student">{t.student}</option><option value="farmer">{t.farmer}</option><option value="woman"><CategoryName category="Women" lang={lang}/></option><option value="small_business"><CategoryName category="Small Business Owners" lang={lang}/></option><option value="general"><CategoryName category="General Public" lang={lang}/></option></select></label>
        <ErrorNotice error={error} onDismiss={() => setError('')}/>
        <div className="eligibility-actions"><button className="primary-button" disabled={busy || !occupation}>{busy ? ui.loading : ui.continue} <span>↗</span></button></div>
      </form>}

      {step === 2 && <form className="assessment-form" onSubmit={continueAssessment}>
        <p className="step-intro">{ui.stepPrompt}</p>
        <div className="profile-question-grid">{visibleQuestions.map(question => <label className="profile-question" key={question.id}><span>{question.label}</span><select value={answers[question.id] || ''} onChange={event => dispatch({ type: 'ANSWER_CHANGED', id: question.id, value: event.target.value })}><option value="">{ui.skip}</option>{question.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>)}</div>
        <p className="privacy-note">{ui.privacy}</p>
        <ErrorNotice error={error} onDismiss={() => setError('')}/>{busy && <LoadingState/>}
        <div className="eligibility-actions"><button type="button" className="secondary-button" disabled={busy} onClick={() => dispatch({ type: 'BACK' })}>{t.back}</button><button className="primary-button" disabled={busy}>{busy ? ui.checking : ui.seeResults} <span>↗</span></button></div>
      </form>}

      {step === 3 && results && <div className="eligibility-results" aria-live="polite">
        <p className="privacy-note">{results.message}</p>
        {noResults ? <div className="no-eligibility-results"><p>{ui.noResults}</p><button className="secondary-button" onClick={() => navigate('/schemes')}>{ui.explore}</button></div> :
          resultGroups.map(([key, title]) => results.groups[key].length > 0 && <section className="assessment-group" key={key}><h3>{title} <span className="category-tag">{results.counts[key]}</span></h3><div className="eligibility-result-grid">{results.groups[key].map(scheme => <article className={`eligibility-result-card status-${scheme.assessment.status}`} key={scheme.id}>
            <span className="category-tag">{scheme.category}</span><h4>{scheme.name}</h4><p className="result-rationale">{scheme.assessment.rationale}</p>
            <strong>{ui.requirements}</strong><ul>{scheme.assessment.eligibility_summary.map((item, index) => <li key={index}>{item}</li>)}</ul>
            <strong>{ui.benefit}</strong><p>{scheme.assessment.benefit_summary}</p>
            {(scheme.assessment.unmet_conditions.length > 0 || scheme.assessment.unknown_conditions.length > 0) && <p className="result-note">{[...scheme.assessment.unmet_conditions, ...scheme.assessment.unknown_conditions].slice(0, 2).join(' ')}</p>}
            <div className="result-meta"><a href={scheme.official_url} target="_blank" rel="noreferrer">{ui.official} ↗</a><small>{ui.verified}: {scheme.last_verified}</small></div>
            <button type="button" className="secondary-button result-details-button" onClick={() => onSelectScheme(scheme)}>{ui.details}</button>
          </article>)}</div></section>)}
        <div className="eligibility-actions"><button className="secondary-button" onClick={() => dispatch({ type: 'BACK' })}>{t.back}</button><button className="primary-button" onClick={checkAgain}>{ui.again}</button></div>
      </div>}
    </div></section>
  )
}

export function AssistantPage({ t, lang }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copiedIdx, setCopiedIdx] = useState(null)
  const [speakingIdx, setSpeakingIdx] = useState(null)

  const voice = useVoiceInput(lang, text => setQuestion(prev => prev ? prev + ' ' + text : text))

  async function submit(e) {
    e.preventDefault()
    if (!question.trim()) return
    const current = question.trim()
    setBusy(true); setError('')
    const historyPayload = history.slice(-6)
    try {
      const answer = await postJson('/assistant', { question: current, language: lang, history: historyPayload }, lang)
      setMessages(items => [...items, { question: current, answer }])
      setHistory(prev => [...prev, { role: 'user', text: current }, { role: 'model', text: answer.answer }])
      setQuestion('')
    } catch (e) { setError(e.message || t.retry) }
    finally { setBusy(false) }
  }

  function clearConversation() { setMessages([]); setHistory([]); setQuestion(''); setError('') }

  function copyAnswer(text, idx) {
    navigator.clipboard?.writeText(text).then(() => {
      setCopiedIdx(idx)
      setTimeout(() => setCopiedIdx(null), 2000)
    })
  }

  function toggleSpeak(text, idx) {
    if (speakingIdx === idx) {
      window.speechSynthesis?.cancel()
      setSpeakingIdx(null)
    } else {
      speakText(text, lang)
      setSpeakingIdx(idx)
      // Auto-clear speaking state after estimated duration
      setTimeout(() => setSpeakingIdx(null), Math.min(text.length * 60, 15000))
    }
  }

  return (
    <section className="page-section content-section">
      <div className="panel assistant-page-panel">
        <div className="panel-heading"><span className="feature-icon">✳</span><span className="eyebrow">03 / GET CLARITY</span><h2>{t.assistant}</h2><p>{t.assistantIntro}</p></div>
        <form onSubmit={submit}>
          <label className="sr-only" htmlFor="question">{t.ask}</label>
          <div className="textarea-row">
            <textarea id="question" value={question} maxLength="1500" onChange={e => setQuestion(e.target.value)} placeholder={t.ask} rows="3"/>
            {voice.supported && (
              <button type="button" className={`voice-btn${voice.listening ? ' voice-btn--active' : ''}`}
                aria-label={t.voiceInput || 'Voice input'} title={t.voiceInput || 'Voice input'}
                onClick={voice.listening ? voice.stop : voice.start}>
                {voice.listening ? '⏹' : '🎤'}
              </button>
            )}
          </div>
          {!voice.supported && <small className="voice-unsupported">Voice input not supported in this browser.</small>}
          <div className="assistant-actions">
            {messages.length > 0 && <button type="button" className="secondary-button" onClick={clearConversation}>{t.clear || 'Clear'}</button>}
            <button className="primary-button" disabled={busy || !question.trim()}>{busy ? 'Thinking…' : t.send}<span>↗</span></button>
          </div>
        </form>
        <ErrorNotice error={error} onDismiss={() => setError('')}/>{busy && <LoadingState/>}
        <div className="conversation" aria-live="polite">
          {messages.map((item, index) => (
            <article className="conversation-turn" key={`${index}-${item.question}`}>
              <p className="user-question">{item.question}</p>
              <div className="answer-card">
                <p>{item.answer.answer}</p>
                {item.answer.uncertain && <small className="uncertainty-note">⚠ {t.deadlineNote}</small>}
                {item.answer.sources && item.answer.sources.length > 0 && (
                  <div className="source-list">
                    <span className="source-label">{t.source || 'Sources'}:</span>
                    {item.answer.sources.map((src, si) => (
                      <a key={`${src.url}-${si}`} href={src.url || '#'} target="_blank" rel="noreferrer"
                        className={`source-link${src.doc_type === 'pdf' ? ' source-link--pdf' : ''}`}>
                        {src.name}{src.page ? ` (p.${src.page})` : ''} ↗
                      </a>
                    ))}
                  </div>
                )}
                {item.answer.rag_used && <small className="rag-badge">✦ Semantically retrieved</small>}
                <div className="answer-actions">
                  <button className="answer-action-btn" aria-label={t.copy || 'Copy'} title={t.copy || 'Copy'}
                    onClick={() => copyAnswer(item.answer.answer, index)}>
                    {copiedIdx === index ? (t.copied || 'Copied!') : (t.copy || 'Copy')}
                  </button>
                  {typeof window !== 'undefined' && window.speechSynthesis && (
                    <button className="answer-action-btn" aria-label={t.speak || 'Read aloud'}
                      onClick={() => toggleSpeak(item.answer.answer, index)}>
                      {speakingIdx === index ? '⏹' : '🔊'}
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
        <p className="privacy-note">Answers use scheme information available in YojanaMitra and link to official sources. Please confirm current rules with the department.</p>
      </div>
    </section>
  )
}

export function DocumentsPage({ t, lang }) {
  const [pdf, setPdf] = useState(null)
  const [summary, setSummary] = useState(null)
  const [ragStatus, setRagStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    if (!pdf) { setError(t.upload); return }
    if (pdf.size > 10 * 1024 * 1024) { setError('This PDF is over the 10 MB limit. Choose a smaller file.'); return }
    setBusy(true); setError(''); setSummary(null); setRagStatus(null)
    try {
      const form = new FormData()
      form.append('file', pdf)
      const result = await request('/documents/summarize', { method: 'POST', body: form }, 'en')
      setSummary(result)
      setRagStatus('indexing')
      try {
        const ragForm = new FormData()
        ragForm.append('file', pdf)
        await request('/rag/ingest', { method: 'POST', body: ragForm }, 'en')
        setRagStatus('indexed')
      } catch { setRagStatus('failed') }
    } catch (e) { setError(e.message || t.retry) }
    finally { setBusy(false) }
  }

  return (
    <section className="page-section content-section">
      <div className="panel document-page-panel">
        <div className="panel-heading"><span className="feature-icon">▧</span><span className="eyebrow">04 / MAKE IT CLEAR</span><h2>{t.docs}</h2><p>{t.docsIntro}</p></div>
        <form onSubmit={submit} className="upload-form">
          <label className="file-picker"><span aria-hidden="true">↑</span><span>{pdf?.name || t.upload}</span><input type="file" accept="application/pdf,.pdf" onChange={e => { setPdf(e.target.files?.[0] || null); setSummary(null); setError(''); setRagStatus(null) }}/></label>
          <button className="primary-button" disabled={busy || !pdf}>{busy ? 'Summarizing…' : t.summarize}<span>↗</span></button>
        </form>
        <ErrorNotice error={error} onDismiss={() => setError('')}/>{busy && <LoadingState/>}
        {summary && (
          <div className="answer-card" aria-live="polite">
            <span className="category-tag">{summary.pages} pages · {summary.filename}</span>
            <div className="pdf-summary-content">
              {summary.summary.split('\n').map((line, i) =>
                line.startsWith('Overview:') || line.startsWith('Eligibility:') || line.startsWith('Benefits:') || line.startsWith('Documents Required:') || line.startsWith('How to Apply:')
                  ? <strong key={i} className="summary-section-label">{line}</strong>
                  : <p key={i}>{line}</p>
              )}
            </div>
            <small>{summary.note}</small>
            {ragStatus === 'indexing' && <small className="rag-badge">⟳ Indexing for semantic search…</small>}
            {ragStatus === 'indexed' && <small className="rag-badge">✦ Indexed — the assistant can now answer questions about this document</small>}
            {ragStatus === 'failed' && <small className="uncertainty-note">⚠ Could not index for semantic search (RAG unavailable)</small>}
          </div>
        )}
      </div>
    </section>
  )
}

export function AboutPage() {
  return (
    <section className="page-section content-section about-page">
      <span className="eyebrow">ABOUT YOJANAMITRA</span>
      <h1>Public support, made easier to understand.</h1>
      <p className="about-lead">YojanaMitra helps people across India discover government schemes, check preliminary eligibility, and understand official documents — in English, Telugu, and Hindi.</p>
      <div className="about-grid">
        <article className="panel"><span className="feature-icon">01</span><h2>Our purpose</h2><p>Government scheme information is spread across dozens of official portals and PDF documents. YojanaMitra brings 23 verified scheme summaries, eligibility guidance, required documents, and official source links together in one clear, accessible place.</p></article>
        <article className="panel"><span className="feature-icon">02</span><h2>Technology</h2><p>Built with React + Vite (frontend) and Python FastAPI (backend). AI answers are powered by Google Gemini 1.5 Flash using a multilingual RAG pipeline with SQLite + sentence-transformers — supporting English, Telugu, and Hindi queries. No user data is stored.</p></article>
        <article className="panel"><span className="feature-icon">03</span><h2>How it helps</h2><p>Search and filter 23 schemes across 5 categories. Use the 3-step eligibility checker to find potential matches. Ask the AI assistant in your language. Upload a scheme PDF for a plain-language summary. All scheme data verified against official portals as of November 2026.</p></article>
        <article className="panel"><span className="feature-icon">04</span><h2>Important notice</h2><p>Results are <strong>preliminary guidance only</strong> — not an official government determination. Scheme rules change. Always verify current eligibility and application details at the official portal before applying. YojanaMitra does not store submitted profile data or uploaded PDFs.</p>
          <div className="about-links"><a href="https://www.myscheme.gov.in/" target="_blank" rel="noreferrer">myScheme.gov.in ↗</a><a href="https://www.india.gov.in/" target="_blank" rel="noreferrer">india.gov.in ↗</a></div>
        </article>
      </div>
    </section>
  )
}

function TrustStrip() {
  return (
    <section className="trust-strip">
      <span className="trust-mark">✳</span>
      <div><strong>Clear guidance. Official information.</strong><p>Scheme rules can change. Always confirm details on the official government portal before applying.</p></div>
      <a href="https://www.myscheme.gov.in/" target="_blank" rel="noreferrer">Explore myScheme ↗</a>
    </section>
  )
}
