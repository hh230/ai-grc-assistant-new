"""Pure change detection: new / updated / removed / unchanged, from a previously known
content hash and a freshly computed one. No I/O — the caller looks up the previous hash via
a repository and passes it in, and reports non-availability explicitly (e.g. a 404 on
re-fetch) rather than this module ever touching the network or a database.

``content_hash`` is the authoritative signal (an exact fingerprint of the normalized text).
The document's URL is compared directly (as the storage layer's lookup key) rather than
hashed — a stable string compares and indexes exactly as well as a hash of it, with no loss of
precision. ``Last-Modified`` HTTP metadata, where a source sends it, is a useful *fast-path*
hint for a crawler adapter to skip re-fetching unchanged content, but it is not authoritative
here: servers are not required to send it, and honesty about content is what "changed" means.
"""

from __future__ import annotations

from enum import Enum


class DocumentChangeType(str, Enum):
    NEW = "new"
    UPDATED = "updated"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


def detect_change(
    *,
    previous_content_hash: str | None,
    current_content_hash: str,
    currently_available: bool = True,
) -> DocumentChangeType:
    """Classify one document's state versus what was last stored for its URL.

    ``currently_available=False`` means the crawler could not re-fetch the document at all
    (e.g. a 404/410) — that always reports ``REMOVED``, regardless of any previous hash.
    """
    if not currently_available:
        return DocumentChangeType.REMOVED
    if previous_content_hash is None:
        return DocumentChangeType.NEW
    if previous_content_hash != current_content_hash:
        return DocumentChangeType.UPDATED
    return DocumentChangeType.UNCHANGED
