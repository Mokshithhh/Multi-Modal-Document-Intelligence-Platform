import { DocumentRecord } from "@/lib/api";

export function StatusBadge({ status }: { status: DocumentRecord["status"] }) {
  const label = status === "COMPLETED" ? "Indexed" : status === "PROCESSING" ? "Processing" : status === "PENDING" ? "Queued" : "Failed";
  return <span className={`status-badge status-${status.toLowerCase()}`}><span />{label}</span>;
}
