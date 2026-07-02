"use client";

import { useState } from "react";
import { Download, FileText, Loader2, Sparkles, Trash2 } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { useDeleteDocument, useDocuments } from "@/hooks/useDocuments";
import { DOCUMENT_CATEGORY_LABELS, type DocumentDto } from "@/lib/documents/types";
import { cn, formatBytes, formatDate } from "@/lib/utils";

interface DocumentListProps {
  canDelete: boolean;
}

export function DocumentList({ canDelete }: DocumentListProps) {
  const { data: documents, isLoading, isError, error } = useDocuments();

  if (isLoading) {
    return (
      <Card className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
        Loading documents…
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="py-10 text-center text-sm text-danger">
        {(error as Error)?.message ?? "Failed to load documents."}
      </Card>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <Card grain className="flex flex-col items-center gap-3 py-14 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
          <FileText className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">No documents yet</p>
          <p className="text-xs text-foreground-muted">
            Upload a PDF or Word document to get started.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card flush>
      <div className="flex items-center justify-between px-5 py-3.5">
        <h2 className="text-sm font-semibold tracking-tight text-foreground">
          Documents
          <span className="ml-2 text-2xs font-normal text-foreground-muted">
            {documents.length} total
          </span>
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-sm">
          <thead>
            <tr className="border-y border-hairline text-left text-2xs uppercase tracking-wider text-foreground-muted">
              <th className="px-5 py-2.5 font-medium">Document</th>
              <th className="px-3 py-2.5 font-medium">Category</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium">Size</th>
              <th className="px-3 py-2.5 font-medium">Uploaded by</th>
              <th className="px-3 py-2.5 font-medium">Date</th>
              <th className="px-5 py-2.5 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} canDelete={canDelete} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DocumentRow({ doc, canDelete }: { doc: DocumentDto; canDelete: boolean }) {
  const deleteMutation = useDeleteDocument();
  const [confirming, setConfirming] = useState(false);

  return (
    <tr className="border-b border-hairline last:border-0 hover:bg-surface-elevated/60">
      <td className="px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-2">
            <FileText className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium text-foreground">{doc.fileName}</p>
            <p className="text-2xs uppercase text-foreground-muted">{doc.kind}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-3">
        <Badge tone="neutral">{DOCUMENT_CATEGORY_LABELS[doc.category]}</Badge>
      </td>
      <td className="px-3 py-3">
        <DocumentStatusBadge status={doc.status} />
      </td>
      <td className="px-3 py-3 text-foreground-secondary">{formatBytes(doc.sizeBytes)}</td>
      <td className="px-3 py-3 text-foreground-secondary">{doc.uploadedByName}</td>
      <td className="px-3 py-3 text-foreground-muted">{formatDate(doc.createdAt)}</td>
      <td className="px-5 py-3">
        <div className="flex items-center justify-end gap-1">
          <Link
            href={`/analysis?doc=${doc.id}`}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-hairline bg-surface/60 px-2 text-2xs font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
            title="Analyze document"
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />
            Analyze
          </Link>
          <a
            href={`/api/documents/${doc.id}/content`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-hairline bg-surface/60 text-foreground-muted transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
            title="Download"
          >
            <Download className="h-3.5 w-3.5" strokeWidth={1.75} />
          </a>
          {canDelete && (
            <button
              type="button"
              onClick={() => {
                if (confirming) deleteMutation.mutate(doc.id);
                else {
                  setConfirming(true);
                  setTimeout(() => setConfirming(false), 3000);
                }
              }}
              disabled={deleteMutation.isPending}
              className={cn(
                "inline-flex h-7 items-center justify-center rounded-md border px-2 text-2xs font-medium transition-colors duration-150",
                confirming
                  ? "border-danger/40 bg-danger-soft text-danger"
                  : "border-hairline bg-surface/60 text-foreground-muted hover:border-hairline-strong hover:text-foreground",
              )}
              title="Delete"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
              ) : (
                <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
              )}
              {confirming && <span className="ml-1">Confirm</span>}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
