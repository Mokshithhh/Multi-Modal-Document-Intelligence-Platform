"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Clock3, FileText, Files, MessageSquareText, Plus, ScanSearch, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api, DocumentRecord, formatBytes, Metrics } from "@/lib/api";
import { PageHeading } from "@/components/PageHeading";
import { StatusBadge } from "@/components/StatusBadge";

const emptyMetrics: Metrics = { documents_total: 0, documents_processing: 0, documents_completed: 0, documents_failed: 0, error_rate: 0, messages_total: 0, estimated_tokens: 0, retrieval_runs: 0, citation_count: 0 };

export default function OverviewPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<DocumentRecord[]>("/documents"), api<Metrics>("/admin/metrics")]).then(([docs, stats]) => { setDocuments(docs); setMetrics(stats); }).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load workspace")).finally(() => setLoading(false));
  }, []);

  return <>
    <PageHeading eyebrow="WORKSPACE OVERVIEW" title="Your workspace" description="A clear view of the knowledge your team is building." action={<Link className="primary-button" href="/documents"><Plus size={17} /> Add documents</Link>} />
    {error && <div className="inline-error" role="alert"><TriangleAlert size={16} />{error}<span>Check that the API is running and try again.</span></div>}
    <section className="welcome-band"><div className="welcome-icon"><Sparkles size={18} /></div><div className="welcome-copy"><span className="welcome-kicker">THE SIGNAL, NOT THE NOISE</span><h2>Your documents are ready to think with.</h2><p>Ask a question across your library or bring in something new.</p></div><Link href="/chat" className="welcome-link" aria-label="Ask your documents"><ArrowUpRight size={19} /></Link><div className="welcome-index">01 <span>/</span> 04</div></section>
    <div className="section-heading"><div><h2>Workspace pulse</h2><p>A live read on the knowledge you’ve connected.</p></div><span className="live-label"><span /> LIVE</span></div>
    {loading ? <div className="metric-grid metric-grid-loading" aria-label="Loading workspace metrics" aria-busy="true">{[0, 1, 2, 3].map((item) => <div className="metric-skeleton" key={item}><span /><i /><i /></div>)}</div> : <section className="metric-grid" aria-label="Workspace metrics">
      <MetricTile label="Documents" value={metrics.documents_total} note={`${metrics.documents_completed} indexed and searchable`} icon={<Files size={17} />} accent="green" />
      <MetricTile label="In the pipeline" value={metrics.documents_processing} note="Being prepared for search" icon={<Clock3 size={17} />} accent="amber" />
      <MetricTile label="Questions asked" value={metrics.messages_total} note={`${metrics.citation_count} source citations returned`} icon={<MessageSquareText size={17} />} accent="coral" />
      <MetricTile label="Tokens processed" value={metrics.estimated_tokens.toLocaleString()} note={`Error rate ${(metrics.error_rate * 100).toFixed(1)}%`} icon={<ScanSearch size={17} />} accent="blue" />
    </section>}
    <section className="content-section document-section"><div className="section-heading"><div><h2>Recently added</h2><p>Your latest source material, with indexing status.</p></div><Link href="/documents" className="text-link">View library <ArrowRight size={15} /></Link></div>
      {documents.length ? <div className="table-wrap"><table className="document-table"><thead><tr><th>DOCUMENT</th><th>SIZE</th><th>ADDED</th><th>STATUS</th><th></th></tr></thead><tbody>{documents.slice(0, 5).map((document) => <tr key={document.id}><td><span className="file-icon"><FileText size={16} /></span><span className="file-name">{document.filename}</span></td><td>{formatBytes(document.file_size)}</td><td>{new Date(document.created_at).toLocaleDateString()}</td><td><StatusBadge status={document.status} /></td><td><ArrowUpRight size={15} className="row-arrow" /></td></tr>)}</tbody></table></div> : <div className="empty-state"><span className="empty-icon"><Files size={19} /></span><div><strong>Your library starts here</strong><p>Upload a document to make its knowledge searchable.</p></div><Link href="/documents" className="text-link">Add a source <ArrowRight size={15} /></Link></div>}
    </section>
    <section className="quick-actions"><Link href="/documents"><span className="quick-icon quick-green"><Plus size={17} /></span><span><strong>Bring in a document</strong><small>PDFs, scans, and image files</small></span><ArrowDownRight size={16} /></Link><Link href="/chat"><span className="quick-icon quick-coral"><MessageSquareText size={17} /></span><span><strong>Ask across your sources</strong><small>Answers with page-level citations</small></span><ArrowDownRight size={16} /></Link></section>
  </>;
}

function MetricTile({ label, value, note, icon, accent }: { label: string; value: string | number; note: string; icon: React.ReactNode; accent: string }) {
  return <article className="metric-tile"><div className={`metric-icon icon-${accent}`}>{icon}</div><p className="metric-label">{label}</p><p className="metric-value">{value}</p><p className="metric-note">{note}</p></article>;
}

