from knowledge_importer.parsers.pdf_backends.base import PdfBackend
from knowledge_importer.parsers.pdf_backends.pypdf_backend import PypdfBackend
from knowledge_importer.parsers.pdf_backends.pypdfium_backend import PypdfiumBackend

# The default backend chain, in priority order: fast/strict first, permissive fallback
# second. A future engine (another library, or OCR for scanned PDFs) is appended here.
DEFAULT_PDF_BACKENDS: tuple[PdfBackend, ...] = (PypdfBackend(), PypdfiumBackend())

__all__ = ["PdfBackend", "PypdfBackend", "PypdfiumBackend", "DEFAULT_PDF_BACKENDS"]
