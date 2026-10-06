import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, Bot, Check, CheckCircle2, ChevronDown, CircleHelp, Clock3, GitBranch, GraduationCap, Headphones, LayoutDashboard, MessageCircle, Play, Quote, RefreshCw, Search, Send, ShieldCheck, Siren, Sparkles, Ticket, Users, WandSparkles, X, XCircle } from 'lucide-react'
import './style.css'

const request = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`)
  return body
}
const post = (path, data) => request(path, { method: 'POST', ...(data === undefined ? {} : { body: JSON.stringify(data) }) })
const title = value => (value || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
const pct = n => `${Math.round((n || 0) * 100)}%`
const duration = n => `${Math.round((n || 0) / 60)}m ${String(Math.round((n || 0) % 60)).padStart(2, '0')}s`

function App() {
  const [page, setPage] = useState('overview')
  const [overview, setOverview] = useState(null)
  const [optimization, setOptimization] = useState({ clusters: [], proposals: [] })
  const [followup, setFollowup] = useState(null)
  const [selected, setSelected] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    Promise.all([request('/overview'), request('/optimization'), request('/followup')])
      .then(([a, b, c]) => { setOverview(a); setOptimization(b); setFollowup(c) })
      .catch(e => setError(e.message))
  }, [])

  const action = async (key, work) => {
    setBusy(key); setError('')
    try { await work() } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const scan = () => action('scan', async () => { setOptimization(await post('/optimization/scan')); setSelected(null); setOverview(await request('/overview')) })
  const prepare = issue => action(`prepare-${issue}`, async () => {
    const packet = await post(`/optimization/proposals/${issue}`)
    setOptimization(prev => ({ ...prev, proposals: [...prev.proposals.filter(p => p.id !== issue), packet] }))
    setSelected(issue)
  })
  const decide = (issue, approved) => action('decision', async () => {
    const packet = await post(`/optimization/proposals/${issue}/decision`, { approved })
    setOptimization(prev => ({ ...prev, proposals: prev.proposals.map(p => p.id === issue ? packet : p) }))
  })
  const start = () => action('start', async () => setFollowup(await post('/followup/start')))
  const tick = () => action('tick', async () => setFollowup(await post('/followup/tick')))
  const ask = q => action('ask', async () => {
    const prompt = (q || question).trim(); if (!prompt) return
    setQuestion(prompt)
    const result = await post('/supervisor/ask', { question: prompt })
    setAnswer(result); setHistory(prev => [{ question: prompt, result }, ...prev].slice(0, 6))
  })

  const packet = optimization.proposals.find(p => p.id === selected)
  const openCases = followup?.cases.filter(c => c.status === 'open').length || 0
  const nav = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'optimization', label: 'CX optimization', icon: WandSparkles },
    { id: 'followup', label: 'Customer follow-up', icon: GitBranch },
    { id: 'supervisor', label: 'Ask your center', icon: MessageCircle },
  ]

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span></span><span></span><span></span></div><div><strong>genesys<span>cloud</span></strong><small>CX AUTOPILOT</small></div></div>
      <div className="workspace-switch"><div className="workspace-avatar">CX</div><div><strong>Experience command</strong><small>Hackathon workspace</small></div><ChevronDown size={15}/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>{nav.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => setPage(item.id)}><item.icon size={18}/><span>{item.label}</span>{item.id === 'optimization' && optimization.proposals.some(p => p.status === 'awaiting_approval') && <i className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="agent-status"><div className="pulse-dot"/><div><strong>Agent network active</strong><small>{overview?.model || 'LLM'} ·</small></div></div><div className="user"><div className="user-avatar">S</div><div><strong>Supervisor</strong><small>Demo environment</small></div><span>•••</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{nav.find(n => n.id === page)?.label}</strong></div><div className="top-actions"><span className="environment"><span/> DEMO MODE</span><button className="icon-btn" title="Notifications" onClick={() => setPage('optimization')}><Bell size={18}/></button><div className="top-avatar">S</div></div></header>
      {error && <div className="error-banner"><CircleHelp size={18}/>{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={16}/></button></div>}
      {page === 'overview' && <div className="content">
        <div className="hero"><div className="hero-copy"><div className="eyebrow light"><Sparkles size={14}/> AUTONOMOUS CONTACT CENTER INTELLIGENCE</div><h1>Your contact center.<br/><em>Continuously improving.</em></h1><p>Discover friction, own every follow-up, and turn operational data into decisions. One workspace for the agents moving customer experience forward.</p><button className="hero-button" onClick={() => setPage('optimization')}>Explore the workflows <ArrowRight size={17}/></button></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orb orb-1"><Activity size={22}/></div><div className="orb orb-2"><Bot size={22}/></div><div className="orb orb-3"><Check size={23}/></div><div className="central-orb"><div className="central-logo"><Sparkles size={37}/></div><span>CX Autopilot</span></div></div></div>
        <div className="section-heading"><div><div className="eyebrow">LIVE SNAPSHOT</div><h2>At a glance</h2></div><span className="data-caption"><span className="pulse-dot"/> Synthesizing Genesys Cloud data</span></div>
        <div className="stats-grid"><Stat icon={Headphones} label="Interactions analyzed" value={overview?.interactions ?? '—'} foot="Across voice & digital"/><Stat icon={GitBranch} label="Customer journeys" value={overview?.flows ?? '—'} foot="Architect flow samples"/><Stat icon={CheckCircle2} label="Resolution rate" value={overview ? pct(overview.stats.resolution_rate) : '—'} foot="Current baseline"/><Stat icon={Clock3} label="Avg. handle time" value={overview ? duration(overview.stats.avg_handle_time_seconds) : '—'} foot="Current baseline"/></div>
        <div className="section-heading usecases-heading"><div><div className="eyebrow">THREE AUTONOMOUS WORKFLOWS</div><h2>Explore what the agents can do</h2></div></div>
        <div className="usecase-grid"><Usecase number="01" icon={WandSparkles} tint="orange" title="Autonomous CX optimization" desc="Find friction, diagnose root causes, simulate improvements, and approve changes with confidence." action="Explore optimization" onClick={() => setPage('optimization')}/><Usecase number="02" icon={GitBranch} tint="purple" title="Customer follow-up" desc="Keep an autonomous owner on unresolved issues from first contact to final resolution." action="View follow-ups" onClick={() => setPage('followup')}/><Usecase number="03" icon={MessageCircle} tint="blue" title="Ask your contact center" desc="Ask operational questions and get an evidence-backed report from specialist analytics agents." action="Ask a question" onClick={() => setPage('supervisor')}/></div>
        <div className="footnote">This demo runs the supplied Python agents against Genesys Cloud interactions and a sample CRM. Changes to Architect flows are simulated in memory.</div>
      </div>}
      {page === 'optimization' && <div className="content">
        <PageHeading kicker="WORKFLOW 01 / AUTONOMOUS CX OPTIMIZATION" title="From friction to better journeys" description="Let specialist agents discover issues, propose an improvement, stress-test it across personas, and submit it for your approval."/>
        <div className="flow-strip">{['Detect', 'Diagnose', 'Fix', 'Simulate', 'Approve', 'Deploy', 'Measure'].map((s, i) => <React.Fragment key={s}><span className={i === 0 ? 'flow-active' : ''}><b>{String(i + 1).padStart(2, '0')}</b>{s}</span>{i < 6 && <ArrowRight size={14}/>}</React.Fragment>)}</div>
        <div className="section-heading"><div><div className="eyebrow">SIGNAL MINING SWARM</div><h2>Friction clusters</h2><p>Patterns discovered across {overview?.interactions || 92} sampled interactions</p></div><button className="primary-button" disabled={!!busy} onClick={scan}>{busy === 'scan' ? <RefreshCw className="spin" size={16}/> : <Search size={16}/>} {optimization.clusters.length ? 'Run scan again' : 'Run signal scan'}</button></div>
        {optimization.clusters.length ? <div className="cluster-grid">{optimization.clusters.map((c, i) => { const p = optimization.proposals.find(v => v.id === c.issue_tag); return <button key={c.issue_tag} className={`cluster-card ${selected === c.issue_tag ? 'selected' : ''}`} onClick={() => p ? setSelected(c.issue_tag) : prepare(c.issue_tag)} disabled={!!busy}><div className="cluster-top"><span className="issue-icon"><Activity size={19}/></span><span className={`priority ${c.customer_impact === 'high' ? 'high' : ''}`}>{c.customer_impact || 'medium'} impact</span></div><h3>{title(c.issue_tag)}</h3><p>{c.summary}</p><div className="cluster-meta"><span><Users size={14}/> {c.stats.count} interactions</span><span>Priority {Math.round(c.priority_score || 0)}</span></div><div className="cluster-link">{p ? p.status === 'deployed' ? 'View measured outcome' : 'Review proposal' : busy === `prepare-${c.issue_tag}` ? 'Agents working…' : 'Diagnose & simulate'} <ArrowRight size={15}/></div></button>})}</div> : <div className="empty-state"><div className="empty-icon"><Search size={25}/></div><h3>No friction scan yet</h3><p>Run the signal-mining swarm to find recurring problems across customer journeys.</p><button className="secondary-button" disabled={!!busy} onClick={scan}>Start analysis <ArrowRight size={16}/></button></div>}
        {packet && <Proposal packet={packet} busy={busy} decide={decide}/>}
      </div>}
      {page === 'followup' && <div className="content">
        <PageHeading kicker="WORKFLOW 02 / AUTONOMOUS CUSTOMER FOLLOW-UP" title="Every case has an owner" description="Persistent agents create backend tickets, check progress, escalate stalled work, and proactively update customers until resolution."/>
        <div className="followup-banner"><div className="followup-banner-icon"><GitBranch size={25}/></div><div><strong>Simulated time, real agent actions</strong><p>Each check-in advances the sample CRM by one day and lets the Python follow-up agents act on every open case.</p></div><button className="primary-button" disabled={!!busy} onClick={followup?.cases.length ? tick : start}>{busy === 'start' || busy === 'tick' ? <RefreshCw className="spin" size={16}/> : <Play size={16}/>} {followup?.cases.length ? openCases ? 'Advance one day' : 'All resolved' : 'Start follow-up demo'}</button></div>
        <div className="mini-stats"><div><span>SIMULATED DAY</span><strong>{followup?.day || 0}</strong></div><div><span>ACTIVE CASES</span><strong>{openCases}</strong></div><div><span>CASES RESOLVED</span><strong>{followup?.cases.filter(c => c.status === 'closed').length || 0}</strong></div><div><span>CUSTOMER UPDATES</span><strong>{followup?.communications.length || 0}</strong></div></div>
        <div className="section-heading"><div><div className="eyebrow">CASE OWNERSHIP</div><h2>Follow-up board</h2></div>{!!followup?.cases.length && <button className="text-button" disabled={!!busy} onClick={start}><RefreshCw size={15}/> Reset demo</button>}</div>
        {followup?.cases.length ? <div className="case-grid">{followup.cases.map(c => <CaseCard key={c.case_id} c={c} state={followup}/>)}</div> : <div className="empty-state"><div className="empty-icon purple"><Ticket size={25}/></div><h3>Ready to own the follow-up</h3><p>Start with sample unresolved interactions. The intake agents will open persistent cases in the CRM.</p><button className="secondary-button" disabled={!!busy} onClick={start}>Start follow-up demo <ArrowRight size={16}/></button></div>}
        {!!followup?.events.length && <div className="timeline-panel"><div className="section-heading compact"><div><div className="eyebrow">AGENT ACTIVITY</div><h2>What happened</h2></div><span className="muted">Latest actions first</span></div><div className="timeline">{[...followup.events].reverse().slice(0, 12).map((e, i) => <div className="timeline-item" key={i}><div className="timeline-dot"/><span className="timeline-day">DAY {e.day}</span><div><strong>{e.type === 'intake' ? 'Case intake' : e.type === 'backend' ? 'Backend update' : `Agent check-in · ${e.case_id}`}</strong><p>{e.detail}</p>{!!e.actions?.length && <div className="tags">{e.actions.map((a, j) => <span key={j}>{title(a)}</span>)}</div>}</div></div>)}</div></div>}
      </div>}
      {page === 'supervisor' && <div className="content supervisor-page">
        <PageHeading kicker="WORKFLOW 03 / AUTONOMOUS SUPERVISOR" title="Ask your contact center" description="Put a question to the planner, analyst, and reporting agents. They pull the relevant sample interaction and workforce data, then return an actionable brief."/>
        <div className="ask-layout"><div className="ask-main"><div className="ask-card"><div className="ask-heading"><div className="ask-icon"><Sparkles size={21}/></div><div><strong>What would you like to know?</strong><p>Ask about trends, friction, sentiment, or workforce performance.</p></div></div><form onSubmit={e => { e.preventDefault(); ask() }}><textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g. What were the major customer issues today?" maxLength={1000}/><div className="ask-footer"><span>Powered by {overview?.model || 'LLM'} agents .</span><button className="primary-button" disabled={!!busy || question.trim().length < 3} type="submit">{busy === 'ask' ? <RefreshCw className="spin" size={16}/> : <Send size={16}/>} Analyze</button></div></form></div>
        {answer && <div className="report-card"><div className="report-header"><span className="report-icon"><Bot size={19}/></span><div><div className="eyebrow">SUPERVISOR REPORT</div><h2>{question}</h2></div><span className="ready-pill"><Check size={13}/> Complete</span></div><div className="report-body"><p>{answer.report?.report}</p></div>{!!answer.report?.escalation_alerts?.length && <EscalationPanel alerts={answer.report.escalation_alerts}/>}{!!answer.report?.coaching_recommendations?.length && <CoachingPanel items={answer.report.coaching_recommendations}/>}{!!answer.report?.recommended_investigation?.length && <div className="recommendations"><strong>Recommended next steps</strong>{answer.report.recommended_investigation.map((item, i) => <div key={i}><span>{String(i + 1).padStart(2, '0')}</span>{item}</div>)}</div>}<div className="sources"><span><GitBranch size={15}/> Analysis plan</span>{answer.plan?.analysis_plan?.map(s => <code key={s}>{title(s)}</code>)}</div><details className="evidence"><summary>View supporting evidence</summary><pre>{JSON.stringify(answer.findings, null, 2)}</pre></details></div>}
        </div><div className="ask-side"><div className="side-card"><div className="eyebrow">GET STARTED</div><h3>Try a question</h3>{['Review all of today’s interactions: identify issues, coach agents on knowledge gaps, and flag any escalation threats.', 'Which customers threatened to escalate to a regulator or consumer forum today?', 'Which agents need coaching on a knowledge gap?', 'What were the major customer issues today?', 'Summarize today’s operational and WFM concerns.'].map((q, i) => <button key={i} disabled={!!busy} onClick={() => ask(q)}><MessageCircle size={16}/>{q}<ArrowUpRight size={15}/></button>)}</div><div className="side-note"><ShieldCheck size={19}/><div><strong>Evidence before answers</strong><p>The planner chooses analytics tools, the analyst gathers data, and the reporter synthesizes the findings.</p></div></div>{!!history.length && <div className="side-card history"><div className="eyebrow">RECENT QUESTIONS</div>{history.map((h, i) => <button key={i} onClick={() => { setQuestion(h.question); setAnswer(h.result) }}>{h.question}<ArrowRight size={14}/></button>)}</div>}</div></div>
      </div>}
    </main>
  </div>
}

function Stat({ icon: Icon, label, value, foot }) { return <div className="stat-card"><div className="stat-icon"><Icon size={20}/></div><span>{label}</span><strong>{value}</strong><small>{foot}</small></div> }
function Usecase({ number, icon: Icon, tint, title: heading, desc, action, onClick }) { return <button className="usecase-card" onClick={onClick}><div className="usecase-top"><span className={`usecase-icon ${tint}`}><Icon size={22}/></span><small>{number} / 03</small></div><h3>{heading}</h3><p>{desc}</p><span className="usecase-link">{action} <ArrowUpRight size={17}/></span></button> }
function PageHeading({ kicker, title: heading, description }) { return <div className="page-heading"><div className="eyebrow">{kicker}</div><h1>{heading}</h1><p>{description}</p></div> }
function MetricCompare({ label, oldValue, newValue, format, lowerBetter }) { const improvement = lowerBetter ? newValue < oldValue : newValue > oldValue; return <div className="metric-compare"><span>{label}</span><div><strong>{format(oldValue)}</strong><ArrowRight size={15}/><strong className={improvement ? 'improved' : ''}>{format(newValue)}</strong></div></div> }
function EscalationPanel({ alerts }) {
  return <div className="escalation-panel">
    <div className="escalation-panel-heading"><Siren size={18}/><strong>Escalation risk - customer threatened to go outside the contact center</strong></div>
    {alerts.map((a, i) => <div key={i} className={`escalation-alert ${a.severity}`}>
      <div className="escalation-alert-top"><span className="escalation-id">{a.interaction_id}</span><span className={`severity-pill ${a.severity}`}>{title(a.severity)} severity</span></div>
      <div className="escalation-quote"><Quote size={14}/><span>{a.customer_quote}</span></div>
      <div className="escalation-meta"><span>Handled by {a.agent_name}</span></div>
      <div className="escalation-action"><strong>Recommended action:</strong> {a.recommended_action}</div>
    </div>)}
  </div>
}
function CoachingPanel({ items }) {
  return <div className="coaching-panel">
    <div className="coaching-panel-heading"><GraduationCap size={18}/><strong>Agent coaching opportunities</strong></div>
    <div className="coaching-grid">{items.map((c, i) => <div key={i} className="coaching-card">
      <div className="coaching-card-top"><div className="person-avatar">{c.agent_name.split(' ').map(s => s[0]).join('')}</div><div><strong>{c.agent_name}</strong><small>{c.team}</small></div></div>
      <span className="coaching-gap-pill"><AlertTriangle size={13}/> {title(c.knowledge_gap)}</span>
      <p>{c.recommendation}</p>
    </div>)}</div>
  </div>
}
function Proposal({ packet, busy, decide }) {
  const { cluster, root_cause: root, fix, simulation, compliance, status } = packet
  const old = simulation.aggregate.old, next = simulation.aggregate.new
  return <section className="proposal"><div className="section-heading"><div><div className="eyebrow">SUPERVISOR REVIEW PACKET</div><h2>{title(cluster.issue_tag)}</h2><p>{title(cluster.flow_name)} · {cluster.stats.count} impacted interactions</p></div><span className={`status-pill ${status}`}>{title(status)}</span></div><div className="proposal-grid"><div className="proposal-block"><span className="block-icon orange"><Search size={18}/></span><div className="eyebrow">ROOT CAUSE</div><h3>{title(root.offending_step_id)}</h3><p>{root.root_cause_explanation}</p><small>Agent confidence: {pct(root.confidence)}</small></div><div className="proposal-block"><span className="block-icon purple"><WandSparkles size={18}/></span><div className="eyebrow">PROPOSED FIX</div><h3>{fix.change_description}</h3><p>{fix.rationale}</p></div><div className="proposal-block"><span className="block-icon green"><ShieldCheck size={18}/></span><div className="eyebrow">COMPLIANCE</div><h3>{title(compliance.verdict)} <span className="risk">{title(compliance.risk_level)} risk</span></h3><p>{compliance.notes}</p>{compliance.violations?.map((v, i) => <small key={i} className="violation">{v}</small>)}</div></div><div className="review-grid"><div className="review-panel"><h3>Flow change preview</h3><p className="muted">Architect flow steps · before and proposed</p><div className="diff"><div><strong>Current flow</strong>{packet.old_steps.map(s => <div key={s.step_id}><small>{s.step_id}</small><span>{s.text}</span></div>)}</div><div><strong>Proposed flow</strong>{fix.proposed_flow_steps?.map(s => <div key={s.step_id}><small>{s.step_id}</small><span>{s.text}</span></div>)}</div></div></div><div className="review-panel"><h3>Adversarial simulation</h3><p className="muted">Average across {simulation.per_persona.length} synthetic personas</p><MetricCompare label="Resolution likelihood" oldValue={old.resolution_likelihood} newValue={next.resolution_likelihood} format={pct}/><MetricCompare label="Customer effort" oldValue={old.effort_score_1_5} newValue={next.effort_score_1_5} format={n => `${n}/5`} lowerBetter/><MetricCompare label="Frustration" oldValue={old.frustration_score_1_5} newValue={next.frustration_score_1_5} format={n => `${n}/5`} lowerBetter/><details className="persona-details"><summary>View persona results</summary>{simulation.per_persona.map(p => <div key={p.persona}><strong>{title(p.persona)}</strong><p>{p.narrative}</p></div>)}</details></div></div>{status === 'awaiting_approval' && <div className="decision-bar"><div><strong>Ready for your decision</strong><p>Approval deploys this change to the in-memory flow registry and measures a simulated new interaction batch.</p></div><div><button className="reject-button" disabled={!!busy} onClick={() => decide(packet.id, false)}><X size={16}/> Reject</button><button className="primary-button" disabled={!!busy} onClick={() => decide(packet.id, true)}><Check size={16}/> Approve & deploy</button></div></div>}{status === 'compliance_blocked' && <div className="decision-bar blocked"><XCircle size={19}/> Compliance flagged this proposal. Deployment is blocked.</div>}{status === 'rejected' && <div className="decision-bar blocked"><XCircle size={19}/> Supervisor rejected this change.</div>}{status === 'deployed' && <div className="measurement"><div><CheckCircle2 size={23}/><div><strong>Change deployed · impact measured</strong><p>{packet.measurement?.impact_summary}</p><small>Recommendation: {title(packet.measurement?.recommendation)}</small></div></div><div className="measurement-stats"><MetricCompare label="Resolution rate" oldValue={packet.before_stats.resolution_rate} newValue={packet.after_stats.resolution_rate} format={pct}/><MetricCompare label="Avg. handle time" oldValue={packet.before_stats.avg_handle_time_seconds} newValue={packet.after_stats.avg_handle_time_seconds} format={duration} lowerBetter/></div></div>}</section>
}
function CaseCard({ c, state }) { const customer = state.customers[c.customer_id], ticket = state.tickets[c.ticket_id], comms = state.communications.filter(m => m.case_id === c.case_id); return <div className="case-card"><div className="case-top"><span className="case-id">{c.case_id}</span><span className={`case-status ${c.status}`}>{c.status === 'closed' ? <Check size={12}/> : <span className="small-pulse"/>}{title(c.status)}</span></div><div className="case-person"><div className="person-avatar">{customer?.name?.split(' ').map(s => s[0]).join('') || 'C'}</div><div><strong>{customer?.name || c.customer_id}</strong><small>{c.customer_id}</small></div></div><h3>{c.summary}</h3><div className="case-facts"><span><Ticket size={15}/> {c.ticket_id || 'Ticket pending'}</span><span><Activity size={15}/> {ticket ? title(ticket.status) : 'Intake complete'}</span></div><div className="case-footer"><span>{title(c.category)} · {title(c.priority)} priority</span><span>{comms.length} update{comms.length === 1 ? '' : 's'} sent</span></div>{!!comms.length && <details><summary>Latest customer message</summary><p>{comms.at(-1).message}</p></details>}</div> }

createRoot(document.getElementById('root')).render(<App />)
