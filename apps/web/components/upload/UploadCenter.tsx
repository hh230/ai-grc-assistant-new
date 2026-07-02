"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Copy,
  FileText,
  Loader2,
  Lock,
  TriangleAlert,
  UploadCloud,
  X,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DocumentList } from "@/components/documents/DocumentList";
import { CategoryPicker } from "@/components/upload/CategoryPicker";
import { DuplicateDocumentDialog } from "@/components/upload/DuplicateDocumentDialog";
import { useRefreshDocuments } from "@/hooks/useDocuments";
import { uploadDocument } from "@/lib/documents/client";
import { ACCEPT_ATTRIBUTE, MAX_UPLOAD_BYTES, validateFileMeta } from "@/lib/documents/validation";
import { DOCUMENT_CATEGORY_LABELS, type DocumentCategory, type DocumentDto } from "@/lib/documents/types";
import { cn, formatBytes } from "@/lib/utils";

interface UploadTask {
  id: string;
  fileName: string;
  sizeBytes: number;
  status: "uploading" | "done" | "duplicate" | "error";
  progress: number;
  error?: string;
}

interface UploadCenterProps {
  canUpload: boolean;
  canDelete: boolean;
}

const MAX_MB = Math.round(MAX_UPLOAD_BYTES / (1024 * 1024));

export function UploadCenter({ canUpload, canDelete }: UploadCenterProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [step, setStep] = useState<"classify" | "upload">("classify");
  const [category, setCategory] = useState<DocumentCategory | null>(null);
  const [dragging, setDragging] = useState(false);
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [duplicateDoc, setDuplicateDoc] = useState<DocumentDto | null>(null);
  const refreshDocuments = useRefreshDocuments();

  function updateTask(id: string, patch: Partial<UploadTask>) {
    setTasks((current) => current.map((task) => (task.id === id ? { ...task, ...patch } : task)));
  }

  function dismissTask(id: string) {
    setTasks((current) => current.filter((task) => task.id !== id));
  }

  async function startUpload(file: File) {
    if (!category) return;
    const id = crypto.randomUUID();
    const validation = validateFileMeta(file.name, file.type, file.size);
    if (!validation.ok) {
      setTasks((c) => [
        {
          id,
          fileName: file.name,
          sizeBytes: file.size,
          status: "error",
          progress: 0,
          error: validation.reason,
        },
        ...c,
      ]);
      return;
    }

    setTasks((c) => [
      { id, fileName: file.name, sizeBytes: file.size, status: "uploading", progress: 0 },
      ...c,
    ]);
    try {
      const result = await uploadDocument(file, category, {
        onProgress: (percent: number) => updateTask(id, { progress: percent }),
      });
      if (result.duplicate) {
        updateTask(id, { status: "duplicate", progress: 100 });
        setDuplicateDoc(result.document);
      } else {
        updateTask(id, { status: "done", progress: 100 });
        refreshDocuments();
        // Auto-clear successful rows after a moment to keep the queue tidy.
        setTimeout(() => dismissTask(id), 2500);
      }
    } catch (error) {
      updateTask(id, {
        status: "error",
        error: error instanceof Error ? error.message : "Upload failed.",
      });
    }
  }

  function handleFiles(fileList: FileList | null | undefined) {
    if (!fileList) return;
    for (const file of Array.from(fileList)) void startUpload(file);
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFiles(event.target.files);
    event.target.value = ""; // allow re-selecting the same file
  }
  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (canUpload) handleFiles(event.dataTransfer.files);
  }

  if (!canUpload) {
    return (
      <div className="space-y-6">
        <Card className="flex items-center gap-3 py-5">
          <Lock className="h-4 w-4 shrink-0 text-foreground-muted" strokeWidth={1.75} />
          <p className="text-sm text-foreground-secondary">
            Your role has read-only access to the Upload Center. Uploading documents requires the
            Analyst, Compliance Manager, or Administrator role.
          </p>
        </Card>
        <DocumentList canDelete={canDelete} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {step === "classify" ? (
        <Card className="space-y-6 p-8">
          <div>
            <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
              Step 1 of 2
            </p>
            <h2 className="mt-1 text-base font-semibold tracking-tight text-foreground">
              What kind of document is this?
            </h2>
            <p className="mt-1 text-sm text-foreground-secondary">
              Classification helps the AI pipeline target the right frameworks and findings.
            </p>
          </div>
          <CategoryPicker value={category} onChange={setCategory} />
          <div className="flex justify-end">
            <button
              type="button"
              disabled={!category}
              onClick={() => setStep("upload")}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
            >
              Continue
              <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
            </button>
          </div>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setStep("classify")}
              className="inline-flex items-center gap-1.5 text-2xs font-medium text-foreground-muted transition-colors duration-150 hover:text-foreground-secondary"
            >
              <ArrowLeft className="h-3.5 w-3.5 flip-rtl" strokeWidth={1.75} />
              Change category
            </button>
            <span className="inline-flex items-center rounded-full border border-hairline bg-surface-2 px-3 py-1 text-2xs font-medium text-foreground-secondary">
              {category ? DOCUMENT_CATEGORY_LABELS[category] : ""}
            </span>
          </div>

          <div
            role="button"
            tabIndex={0}
            aria-label="Upload documents"
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragging(false);
            }}
            onDrop={onDrop}
            className={cn(
              "group flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 py-12 text-center outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-accent/40",
              dragging
                ? "border-accent/60 bg-accent-soft"
                : "border-hairline-strong bg-surface hover:border-foreground-muted/40 hover:bg-surface-2",
            )}
          >
            <span
              className={cn(
                "flex h-14 w-14 items-center justify-center rounded-2xl border transition-colors duration-200",
                dragging ? "border-accent/40 bg-accent-soft" : "border-hairline bg-surface-2",
              )}
            >
              <UploadCloud
                className={cn(
                  "h-6 w-6",
                  dragging ? "text-accent-foreground" : "text-foreground-secondary",
                )}
                strokeWidth={1.5}
              />
            </span>
            <h2 className="mt-4 text-base font-semibold tracking-tight text-foreground">
              {dragging ? "Drop to upload" : "Drag & drop documents"}
            </h2>
            <p className="mt-1 text-sm text-foreground-secondary">
              or{" "}
              <span className="font-medium text-accent-foreground underline-offset-2 group-hover:underline">
                browse your files
              </span>
            </p>
            <p className="mt-3 text-2xs text-foreground-muted">
              PDF or Word (.doc, .docx) · up to {MAX_MB} MB each
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ACCEPT_ATTRIBUTE}
              onChange={onInputChange}
              className="hidden"
            />
          </div>
        </>
      )}

      {tasks.length > 0 && (
        <div className="space-y-2">
          {tasks.map((task) => (
            <UploadTaskRow key={task.id} task={task} onDismiss={() => dismissTask(task.id)} />
          ))}
        </div>
      )}

      <DocumentList canDelete={canDelete} />

      <DuplicateDocumentDialog document={duplicateDoc} onClose={() => setDuplicateDoc(null)} />
    </div>
  );
}

function UploadTaskRow({ task, onDismiss }: { task: UploadTask; onDismiss: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-hairline bg-surface px-4 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-2">
        {task.status === "done" ? (
          <CheckCircle2 className="h-4 w-4 text-success" strokeWidth={1.75} />
        ) : task.status === "duplicate" ? (
          <Copy className="h-4 w-4 text-foreground-muted" strokeWidth={1.75} />
        ) : task.status === "error" ? (
          <TriangleAlert className="h-4 w-4 text-danger" strokeWidth={1.75} />
        ) : (
          <FileText className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <p className="truncate text-sm font-medium text-foreground">{task.fileName}</p>
          <span className="shrink-0 text-2xs text-foreground-muted">
            {task.status === "uploading"
              ? `${task.progress}%`
              : task.status === "done"
                ? "Uploaded"
                : task.status === "duplicate"
                  ? "Already exists"
                  : formatBytes(task.sizeBytes)}
          </span>
        </div>
        {task.status === "error" ? (
          <p className="mt-1 text-2xs text-danger">{task.error}</p>
        ) : (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-surface-elevated">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-200",
                task.status === "done"
                  ? "bg-success"
                  : task.status === "duplicate"
                    ? "bg-foreground-muted"
                    : "bg-accent",
              )}
              style={{ width: `${task.progress}%` }}
            />
          </div>
        )}
      </div>
      {(task.status === "error" || task.status === "done" || task.status === "duplicate") && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md p-1 text-foreground-muted transition-colors duration-150 hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" strokeWidth={1.75} />
        </button>
      )}
    </div>
  );
}
