import { useRef, useState } from "react";
import {
  Sparkles, House, Plus, History, Settings, FileText, FolderOpen,
  UploadCloud, Image as ImageIcon, FileCheck2, Check, ChevronRight,
  Circle, CircleCheck, SlidersHorizontal, Download, X, ShieldCheck,
  Zap, ArrowUpRight, ClipboardCheck, FileArchive, ListChecks, AlertTriangle,
  RefreshCw, Bot
} from "lucide-react";
import Chatbot from "./Chatbot.jsx";

const workflow = [
  { title: "Understand", subtitle: "Extract requirements", icon: FileText },
  { title: "Plan", subtitle: "Create task plan", icon: ListChecks },
  { title: "Execute", subtitle: "Process documents", icon: Settings },
  { title: "Verify", subtitle: "Check every output", icon: ClipboardCheck },
  { title: "Deliver", subtitle: "Package & report", icon: FileArchive }
];

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileKind(file) {
  if (file.type.startsWith("image/")) return "image";
  if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) return "pdf";
  return "other";
}

export default function App() {
  const [activeNav, setActiveNav] = useState("Home");
  const [notice, setNotice] = useState(null);
  const [docs, setDocs] = useState([]);
  const [stage, setStage] = useState(-1);
  const [processing, setProcessing] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const noticeRef = useRef(null);
  const docsRef = useRef(null);
  const timerRef = useRef(null);

  const progress = stage < 0 ? 0 : [12, 28, 60, 82, 100][Math.min(stage, 4)];
  const statusLabel = stage < 0 ? "Waiting to start" : stage === 4 ? "Package is ready" :
    ["Reading notice…", "Building task plan…", "Processing files…", "Verifying outputs…"][stage];

  function addFiles(fileList, target) {
    const incoming = Array.from(fileList || []);
    if (target === "notice") {
      const f = incoming.find(x => /\.(pdf|png|jpe?g)$/i.test(x.name));
      if (f) setNotice({ name: f.name, size: formatSize(f.size), file: f });
      return;
    }
    const accepted = incoming.filter(f => /\.(pdf|png|jpe?g|docx?)$/i.test(f.name));
    setDocs(prev => [...prev, ...accepted.map((f, i) => ({
      id: `${Date.now()}-${i}-${f.name}`,
      name: f.name,
      size: formatSize(f.size),
      type: fileKind(f),
      status: "Ready",
      file: f
    }))]);
  }

  function startProcessing() {
    if (!notice || processing) {
      if (!notice) setShowHelp(true);
      return;
    }
    setProcessing(true);
    setStage(0);
    let next = 0;
    const tick = () => {
      next += 1;
      setStage(next);
      if (next < 4) timerRef.current = window.setTimeout(tick, 1000);
      else {
        setProcessing(false);
        setDocs(prev => prev.map(d => ({ ...d, status: "Verified" })));
      }
    };
    timerRef.current = window.setTimeout(tick, 1000);
  }

  function downloadReport() {
    const report = [
      "DocMitra — Application Preparation Report",
      "==========================================",
      `Generated: ${new Date().toLocaleString()}`,
      `Application notice: ${notice?.name || "Not uploaded"}`,
      "",
      "Files",
      ...docs.map(d => `- ${d.name} | ${d.size} | ${stage === 4 ? "Verified in demo" : "Not yet verified"}`),
      "",
      "Workflow status",
      ...workflow.map((w, i) => `${i + 1}. ${w.title}: ${stage >= i ? "Complete (demo)" : "Pending"}`),
      "",
      "This frontend prototype simulates processing. Connect a backend for real OCR, image resizing, PDF compression, validation and ZIP packaging."
    ].join("\n");
    const url = URL.createObjectURL(new Blob([report], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "DocMitra-status-report.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  const navItems = [
    { label: "Home", icon: House },
    { label: "New Application", icon: Plus },
    { label: "History", icon: History },
    { label: "Settings", icon: Settings }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Sparkles size={24} /></div>
          <div><div className="brand-name">Doc<span>Mitra</span></div><div className="brand-tag">Your application, simplified</div></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {navItems.map(({ label, icon: Icon }) => (
            <button key={label} className={`nav-item ${activeNav === label ? "active" : ""}`}
              onClick={() => {
                setActiveNav(label);
                if (label === "New Application") document.getElementById("new-application")?.scrollIntoView({ behavior: "smooth" });
              }}>
              <Icon size={19} /><span>{label}</span>
              {label === "History" && <span className="nav-count">0</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-art"><FileCheck2 size={42} /></div>
          <p>From complex instructions<br />to a ready-to-review package.</p>
          <div className="sidebar-pill"><span className="status-dot" /> AI assistant ready</div>
        </div>
        <div className="sidebar-footer"><ShieldCheck size={15} /> Your files stay yours</div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{activeNav}</strong></div>
          <div className="secure-label"><ShieldCheck size={15} /> Private workspace</div>
        </header>

        <div className="content">
          <section className="welcome-banner">
            <div className="banner-copy">
              <div className="eyebrow"><Sparkles size={14} /> YOUR AI APPLICATION ASSISTANT</div>
              <h1>Less paperwork.<br /><span>More possibilities.</span></h1>
              <p>Upload an official notice and your existing documents. DocMitra turns requirements into an actionable plan, prepares your files, and checks them before you submit.</p>
              <button className="primary-button" onClick={() => document.getElementById("new-application")?.scrollIntoView({ behavior: "smooth" })}>Start an application <ArrowUpRight size={17} /></button>
            </div>
            <div className="banner-visual" aria-hidden="true">
              <div className="visual-orbit" />
              <div className="visual-document"><FileText size={46} /><i /><i /><i /></div>
              <div className="visual-ai"><Sparkles size={28} /><span>AI</span></div>
              <div className="visual-tag"><Check size={15} /> Verified files</div>
            </div>
          </section>

          <div className="dashboard-grid">
            <div className="left-column">
              <section className="panel upload-panel" id="new-application">
                <div className="section-heading">
                  <div className="step-number">01</div>
                  <div><h2>Start a new application</h2><p>Bring the official instructions and the documents you already have.</p></div>
                  <span className="optional-tag">2 upload areas</span>
                </div>
                {showHelp && !notice && <div className="inline-alert"><AlertTriangle size={16} /> Upload an official notice first so the demo can start the workflow.</div>}
                <div className="upload-grid">
                  <div className="upload-card">
                    <div className="upload-card-head"><div className="upload-icon"><FileText size={20} /></div><div><h3>Official application notice</h3><p>Scholarship or government scheme guidelines</p></div></div>
                    <input ref={noticeRef} type="file" accept=".pdf,.png,.jpg,.jpeg" hidden onChange={e => addFiles(e.target.files, "notice")} />
                    <button className={`dropzone ${notice ? "has-file" : ""}`} onClick={() => noticeRef.current?.click()}>
                      <UploadCloud size={27} /><strong>{notice ? notice.name : "Click to upload or drag and drop"}</strong><small>PDF, PNG or JPG · Max 10 MB</small>
                    </button>
                    {notice && <div className="file-row"><FileText size={18} /><span>{notice.size}</span><button className="remove-button" onClick={() => { setNotice(null); setStage(-1); }}><X size={16} /></button></div>}
                    <div className="upload-tip"><ShieldCheck size={14} /> We’ll use this notice as the source of requirements.</div>
                  </div>
                  <div className="upload-card">
                    <div className="upload-card-head"><div className="upload-icon"><FolderOpen size={20} /></div><div><h3>Your existing documents</h3><p>Photos, identity proof, marksheets and more</p></div></div>
                    <input ref={docsRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" hidden onChange={e => addFiles(e.target.files, "docs")} />
                    <button className="dropzone" onClick={() => docsRef.current?.click()}><UploadCloud size={27} /><strong>Add your files or drag and drop</strong><small>PDF, PNG, JPG, DOCX · 20 MB each</small></button>
                    <div className="file-list">
                      {docs.length === 0 ? <div className="empty-files">No documents added yet.</div> : docs.map(file => (
                        <div className="file-row" key={file.id}>
                          {file.type === "image" ? <ImageIcon size={18} /> : <FileText size={18} />}
                          <div className="file-details"><strong>{file.name}</strong><span>{file.size} · {file.status}</span></div>
                          <button className="remove-button" onClick={() => setDocs(prev => prev.filter(d => d.id !== file.id))} aria-label={`Remove ${file.name}`}><X size={15} /></button>
                        </div>
                      ))}
                    </div>
                    <div className="upload-tip"><Zap size={14} /> Files are processed after you start the workflow.</div>
                  </div>
                </div>
                <div className="upload-actions"><span><b>*</b> Official notice required to begin</span><button className="primary-button" onClick={startProcessing} disabled={processing}>{processing ? <><RefreshCw className="spin" size={16} /> Processing…</> : stage === 4 ? "Run demo again" : <>Analyze & prepare <ChevronRight size={17} /></>}</button></div>
              </section>

              <section className="panel workflow-panel">
                <div className="section-heading"><div className="step-number">02</div><div><h2>Your workflow</h2><p>Follow each step from understanding requirements to delivery.</p></div><span className="live-tag">{processing ? "LIVE DEMO" : stage === 4 ? "COMPLETED" : "READY"}</span></div>
                <div className="workflow-list">
                  {workflow.map((item, i) => {
                    const Icon = item.icon;
                    const done = stage > i;
                    const current = stage === i;
                    return <div className={`workflow-item ${done ? "done" : ""} ${current ? "current" : ""}`} key={item.title}>
                      <div className="workflow-icon">{done ? <Check size={20} /> : <Icon size={20} />}</div>
                      <div><strong>{item.title}</strong><p>{item.subtitle}</p><small>{done ? "Completed (demo)" : current ? "In progress" : "Pending"}</small></div>
                    </div>;
                  })}
                </div>
                {stage >= 0 && <div className="workflow-message"><Bot size={20} /><div><strong>{statusLabel}</strong><p>{stage === 4 ? "Demo complete. Download the report to review the summary." : "This is a simulated workflow. Real processing requires the backend."}</p></div></div>}
              </section>

              <section className="panel requirements-panel">
                <div className="section-heading"><div className="step-number">03</div><div><h2>What will be checked?</h2><p>Validation targets should be based on the selected notice.</p></div></div>
                <div className="checks-grid">
                  <div><ImageIcon /><strong>Photo specifications</strong><span>Dimensions, framing, format and size</span></div>
                  <div><FileText /><strong>PDF requirements</strong><span>File size and basic integrity</span></div>
                  <div><FolderOpen /><strong>File organization</strong><span>Consistent names and folder structure</span></div>
                  <div><ClipboardCheck /><strong>Final validation</strong><span>Pass, retry or flag for review</span></div>
                </div>
              </section>
            </div>

            <aside className="right-column">
              <section className="panel progress-panel">
                <h2>Application progress</h2>
                <div className="progress-content"><div className="progress-ring" style={{ "--progress": `${progress * 3.6}deg` }}><div><strong>{progress}%</strong><span>complete</span></div></div><div><strong>{statusLabel}</strong><p>{stage === 4 ? "Your demo workflow has finished." : "Your workspace is ready when you are."}</p></div></div>
                <div className="progress-bar"><span style={{ width: `${progress}%` }} /></div>
                <div className="progress-foot"><span>Workflow status</span><strong>{stage < 0 ? "Not started" : stage === 4 ? "Complete" : "In progress"}</strong></div>
              </section>
              <section className="panel checklist-panel">
                <h2><Sparkles size={17} /> Task checklist <span>{stage < 0 ? "0/5" : `${stage + 1}/5`}</span></h2>
                {["Extract notice requirements", "Build a structured task plan", "Process photos and PDFs", "Verify output specifications", "Prepare package and README"].map((task, i) => <div className="task-row" key={task}>{stage > i ? <CircleCheck size={17} /> : <Circle size={17} />}<span>{task}</span></div>)}
              </section>
              <section className="panel files-summary-panel">
                <h2>Files summary</h2>
                <div className="summary-row"><ImageIcon size={17} /><span>Images</span><strong>{docs.filter(d => d.type === "image").length}</strong></div>
                <div className="summary-row"><FileText size={17} /><span>PDF documents</span><strong>{docs.filter(d => d.type === "pdf").length}</strong></div>
                <div className="summary-row"><FileCheck2 size={17} /><span>Other files</span><strong>{docs.filter(d => d.type === "other").length}</strong></div>
                <div className="summary-row"><span>Notice uploaded</span><strong>{notice ? "Yes" : "Not yet"}</strong></div>
              </section>
              <button className="download-button" onClick={downloadReport}><Download size={17} /> Download status report <span>.TXT</span></button>
            </aside>
          </div>
          <footer className="page-footer"><span>© 2026 DocMitra</span><span><ShieldCheck size={14} /> Designed for careful, user-reviewed applications</span><span>Prototype interface · Not an official government service</span></footer>
        </div>
      </main>
      <Chatbot />
    </div>
  );
}