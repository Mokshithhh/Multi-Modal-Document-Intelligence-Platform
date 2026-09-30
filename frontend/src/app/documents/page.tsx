"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowDownToLine, ArrowUpRight, CheckCircle2, FileImage, FileText, FolderOpen, LoaderCircle, Plus, RefreshCw, Trash2, TriangleAlert, UploadCloud } from "lucide-react";
import { PageHeading } from "@/components/PageHeading";
import { StatusBadge } from "@/components/StatusBadge";
import { api, DocumentRecord, formatBytes } from "@/lib/api";

export default function DocumentsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDocuments = useCallback(async () => {
    try { setDocuments(await api<DocumentRecord[]>("/documents")); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load documents"); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadDocuments(); const timer = window.setInterval(() => void loadDocuments(), 4000); return () => window.clearInterval(timer); }, [loadDocuments]);

  async function uploadFiles(files: FileList | File[]) {
    const selected = Array.from(files);
    if (!selected.length) return;
    setUploading(true); setError(""); setNotice("");
    for (const file of selected) {
      const body = new FormData(); body.append("file", file);
      try {
        await api<DocumentRecord>("/documents/upload", { method: "POST", body });
        setNotice(`${file.name} added to the processing queue.`);
      } catch (cause) { setError(`${file.name}: ${cause instanceof Error ? cause.message : "Upload failed"}`); }
    }
    setUploading(false);
    await loadDocuments();
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) { if (event.target.files) void uploadFiles(event.target.files); event.target.value = ""; }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); void uploadFiles(event.dataTransfer.files); }
  async function removeDocument(document: DocumentRecord) {
    if (!window.confirm(`Delete “${document.filename}” and its indexed content?`)) return;
    try { await api(`/documents/${document.id}`, { method: "DELETE" }); await loadDocuments(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to delete document"); }
  }

  return <>
    <PageHeading eyebrow="SOURCE LIBRARY" title="Documents" description="Bring your files in. Vanco handles the parsing, OCR, and indexing." action={<button className="primary-button" onClick={() => inputRef.current?.click()}><Plus size={17} /> Add files</button>} />
    <input ref={inputRef} className="visually-hidden" type="file" accept="application/pdf,image/png,image/jpeg,image/tiff,image/webp" multiple onChange={onInput} />
    {error && <div className="inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
    {notice && <div className="inline-success" role="status"><CheckCircle2 size={16} />{notice}</div>}
    <div className="documents-layout">
      <div className={`drop-zone ${dragging ? "drop-zone-active" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} onDrop={onDrop}>
        <span className="drop-icon">{uploading ? <LoaderCircle className="spin" size={22} /> : <UploadCloud size={22} />}</span><h2>{uploading ? "Adding to your library" : "Drop your files here"}</h2><p>PDF, PNG, JPG, TIFF, or WebP <span>·</span> up to 25 MB each</p><button className="secondary-button" onClick={() => inputRef.current?.click()} disabled={uploading}><FolderOpen size={16} /> Browse files</button><span className="drop-encryption"><span /> Files are private to your workspace</span>
      </div>
      <section className="content-section library-section"><div className="section-heading"><div><h2>All sources <span className="count-pill">{documents.length}</span></h2><p>Files are searchable once indexing is complete.</p></div><button className="icon-button bordered-icon" title="Refresh library" onClick={() => void loadDocuments()}><RefreshCw size={15} /></button></div>
        {loading ? <div className="library-empty" aria-busy="true"><div className="empty-icon"><RefreshCw className="spin" size={18} /></div><strong>Loading sources</strong><p>Checking what is connected to this workspace.</p></div> : error && !documents.length ? <div className="library-empty"><div className="empty-icon"><TriangleAlert size={18} /></div><strong>Sources could not be loaded</strong><p>Check the connection, then try again.</p><button className="text-link library-retry" onClick={() => void loadDocuments()}>Retry <RefreshCw size={13} /></button></div> : documents.length ? <div className="table-wrap"><table className="document-table library-table"><thead><tr><th>DOCUMENT</th><th>FILE TYPE</th><th>SIZE</th><th>ADDED</th><th>STATUS</th><th></th></tr></thead><tbody>{documents.map((document) => <tr key={document.id}><td><span className="file-icon">{document.file_type.startsWith("image/") ? <FileImage size={16} /> : <FileText size={16} />}</span><span className="file-details"><strong className="file-name">{document.filename}</strong>{document.status === "FAILED" && document.error_message && <small className="file-error">{document.error_message}</small>}</span></td><td className="type-cell">{document.file_type.split("/").pop()?.toUpperCase()}</td><td>{formatBytes(document.file_size)}</td><td>{new Date(document.created_at).toLocaleDateString()}</td><td><StatusBadge status={document.status} /></td><td><button className="icon-button delete-button" title={`Delete ${document.filename}`} aria-label={`Delete ${document.filename}`} onClick={() => void removeDocument(document)}><Trash2 size={15} /></button></td></tr>)}</tbody></table></div> : <div className="library-empty"><div className="empty-icon"><ArrowDownToLine size={18} /></div><strong>No documents yet</strong><p>Upload your first file to make this space useful.</p></div>}
      </section>
    </div>
    <div className="pipeline-note"><span className="pipeline-icon"><RefreshCw size={15} /></span><span><strong>Indexing runs automatically</strong><small>Text extraction, OCR, chunking, and semantic indexing are handled in the background.</small></span><ArrowUpRight size={15} /></div>
  </>;
}
