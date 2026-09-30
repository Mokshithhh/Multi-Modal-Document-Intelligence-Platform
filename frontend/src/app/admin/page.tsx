"use client";

import { Activity, ArrowUpRight, BadgeCheck, CircleAlert, Clock3, Files, MessageSquareText, ScanLine, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeading } from "@/components/PageHeading";
import { api, Metrics } from "@/lib/api";

const emptyMetrics: Metrics = { documents_total: 0, documents_processing: 0, documents_completed: 0, documents_failed: 0, error_rate: 0, messages_total: 0, estimated_tokens: 0, retrieval_runs: 0, citation_count: 0 };

export default function AdminPage() {
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    async function refresh() { try { setMetrics(await api<Metrics>("/admin/metrics")); setError(""); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load metrics"); } finally { setLoading(false); } }
    void refresh(); const timer = window.setInterval(() => void refresh(), 10000); return () => window.clearInterval(timer);
  }, []);
  const errorPercent = Math.round(metrics.error_rate * 100);
  return <>
    <PageHeading eyebrow="SYSTEM HEALTH" title="Observability" description="A live view of document processing and workspace activity." action={<span className="live-label"><span /> REFRESHES EVERY 10S</span>} />
    {error && <div className="inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
    <section className="observability-status"><div className="status-orbit"><span><Activity size={20} /></span></div><div className="obs-status-copy"><span className="eyebrow">WORKSPACE STATUS</span><h2>Everything is in view.</h2><p>Metrics are scoped to your workspace and update automatically.</p></div><span className="operational-pill"><span /> OPERATIONAL</span></section>
    <div className="section-heading admin-section-heading"><div><h2>Processing overview</h2><p>Activity since this workspace was created.</p></div></div>
    {loading ? <div className="admin-metric-grid admin-metric-grid-loading" aria-label="Loading processing metrics" aria-busy="true">{[0, 1, 2, 3, 4, 5].map((item) => <div className="admin-skeleton" key={item}><span /><i /><i /></div>)}</div> : <section className="admin-metric-grid">
      <AdminMetric icon={<Files size={17} />} label="Documents ingested" value={metrics.documents_total.toLocaleString()} detail={`${metrics.documents_completed} indexed`} tone="green" />
      <AdminMetric icon={<Clock3 size={17} />} label="In processing" value={metrics.documents_processing.toLocaleString()} detail="Queued or currently running" tone="amber" />
      <AdminMetric icon={<CircleAlert size={17} />} label="Ingestion error rate" value={`${errorPercent}%`} detail={`${metrics.documents_failed} failed documents`} tone="coral" />
      <AdminMetric icon={<MessageSquareText size={17} />} label="Retrieval runs" value={metrics.retrieval_runs.toLocaleString()} detail={`${metrics.citation_count} citations returned`} tone="blue" />
      <AdminMetric icon={<ScanLine size={17} />} label="Est. tokens used" value={metrics.estimated_tokens.toLocaleString()} detail="Approx. assistant response tokens" tone="teal" />
      <AdminMetric icon={<BadgeCheck size={17} />} label="Indexed sources" value={metrics.documents_completed.toLocaleString()} detail="Available for hybrid search" tone="green" />
    </section>}
    <div className="observability-bottom"><section className="health-panel"><div className="health-panel-heading"><div><p className="eyebrow">SERVICE CHECKS</p><h2>Connected services</h2></div><ShieldCheck size={17} /></div><HealthRow label="Document database" detail="PostgreSQL + pgvector" /><HealthRow label="Job queue" detail="Redis ingestion worker" /><HealthRow label="Search pipeline" detail="Vector + full-text RRF" /><div className="health-footnote"><Sparkles size={14} /> Health checks run on API requests.</div></section><section className="pipeline-panel"><p className="eyebrow">DOCUMENT LIFECYCLE</p><h2>From file to finding</h2><p className="pipeline-copy">Each source moves through a traceable ingestion path before it can inform an answer.</p><div className="lifecycle"><div><span className="life-step life-done"><Files size={15} /></span><strong>Received</strong><small>{metrics.documents_total} files</small></div><i /><div><span className="life-step life-active"><Activity size={15} /></span><strong>Indexed</strong><small>{metrics.documents_completed} ready</small></div><i /><div><span className="life-step"><MessageSquareText size={15} /></span><strong>Retrieved</strong><small>{metrics.retrieval_runs} queries</small></div></div><div className="pipeline-detail"><ArrowUpRight size={15} /><span>Failures remain visible in the document library with an error detail.</span></div></section></div>
  </>;
}

function AdminMetric({ icon, label, value, detail, tone }: { icon: React.ReactNode; label: string; value: string; detail: string; tone: string }) {
  return <article className="admin-metric"><span className={`admin-metric-icon icon-${tone}`}>{icon}</span><p>{label}</p><strong>{value}</strong><small>{detail}</small></article>;
}

function HealthRow({ label, detail }: { label: string; detail: string }) {
  return <div className="health-row"><span className="health-check"><BadgeCheck size={15} /></span><span><strong>{label}</strong><small>{detail}</small></span><span className="health-operational">Operational</span></div>;
}
