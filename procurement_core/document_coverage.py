"""Shared by the host validator and the embedded document processor."""


def document_coverage(documents, warnings=None):
    files = [item for item in documents if item.get("is_tender_document", (
        item.get("extract_method") != "inline"
        and item.get("source") not in {"apc_external_page", "apc_details", "canadabuys_notice", "sample"}
    ))]
    extracted = [item for item in files if item.get("status") == "extracted" and item.get("text_length", 0) > 0]
    incomplete = [item for item in files if item not in extracted or item.get("truncated")]
    status = "notice_only" if not extracted else "partial" if incomplete or warnings else "complete"
    return {
        "status": status,
        "complete": status == "complete",
        "expected_documents": len(files),
        "extracted_documents": len(extracted),
        "incomplete_documents": len(incomplete),
        "issues": [
            {"document_id": item.get("document_id", ""), "name": item.get("name", ""),
             "status": item.get("status", "unknown"), "reason": item.get("error") or
             ("Extraction was truncated." if item.get("truncated") else "No document text was extracted.")}
            for item in incomplete
        ],
    }


def coverage_warnings(coverage):
    if coverage["complete"]:
        return []
    messages = [
        f"Document coverage: {coverage['status']}; {coverage['extracted_documents']} of "
        f"{coverage['expected_documents']} procurement files extracted. This is not a complete document review."
    ]
    messages.extend(f"{item['name']}: {item['status']} — {item['reason']}" for item in coverage["issues"])
    return messages
