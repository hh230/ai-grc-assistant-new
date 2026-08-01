import Link from "next/link";

export default function DocumentNotFound() {
  return (
    <main className="shell">
      <Link className="back-link" href="/">← Knowledge Center</Link>
      <div className="topbar">
        <div className="brand">
          <span className="eyebrow">Document detail</span>
          <h1>Document not found</h1>
        </div>
      </div>
      <p className="section-note">
        No manifest exists for that document id. It may not have been discovered by the
        import pipeline, or the id in the URL is incorrect.
      </p>
    </main>
  );
}
