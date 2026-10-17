"""Deterministic audit rules over normalized documents. Python owns truth: no model calls.

Exports:
    run_audit(bill, eob=None, estimate=None) -> AuditResult(findings, limitations)
    audit_documents(bill, eob=None, estimate=None) -> list[Finding]
    evidence_problems(findings, documents) -> list[str]
    format_usd(cents) -> "$1,234.56"

Rules:
    R1_BILL_TOTAL_ARITHMETIC               bill line items vs. printed total charges
    R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH bill amount due vs. matching EOB patient responsibility
    R3_POSSIBLE_DUPLICATE_LINE_ITEM        same-looking repeated bill lines
    R5_MISSING_INFORMATION                 checks that could not run

Principles: compare only like-for-like integer-cent values; when completeness or
semantics are unclear, report a limitation or ``insufficient_information`` instead
of asserting a discrepancy; a difference is a reason to ask, never proof of error.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.schemas import (
    DocumentKind,
    DocumentSummary,
    EvidenceRef,
    ExtractionQuality,
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    LineItem,
)

R1_BILL_TOTAL_ARITHMETIC = "R1_BILL_TOTAL_ARITHMETIC"
R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH = "R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH"
R3_POSSIBLE_DUPLICATE_LINE_ITEM = "R3_POSSIBLE_DUPLICATE_LINE_ITEM"
R5_MISSING_INFORMATION = "R5_MISSING_INFORMATION"

# Differences at or above this many cents are "medium" severity; smaller ones "low".
MEDIUM_DIFFERENCE_CENTS = 5000

BASE_LIMITATIONS = [
    "ClearBill runs a limited set of automated checks (bill arithmetic, bill vs. EOB "
    "comparison, and possible repeated charges). A flagged difference is a reason to ask "
    "questions, not proof of a billing error, and an absence of flags does not mean a bill "
    "is correct.",
    "Amounts were read from your documents by AI and may contain mistakes. Verify every "
    "figure against the original documents.",
]

SAFETY_DISCLAIMER = (
    "Demo prototype. Do not upload real medical records. This tool flags possible "
    "discrepancies for review and is not medical, insurance, or legal advice."
)

_PENDING_STATUS_WORDS = (
    "pending", "in process", "processing", "in review", "under review", "received",
    "submitted", "suspended", "open", "not final", "unprocessed",
)
_FINAL_STATUS_WORDS = (
    "final", "processed", "paid", "complete", "closed", "adjudicated", "denied",
)
_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth"]
_TIMES = {1: "once", 2: "twice", 3: "three times"}


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def audit_documents(
    bill: DocumentSummary,
    eob: DocumentSummary | None = None,
    estimate: DocumentSummary | None = None,
) -> list[Finding]:
    return run_audit(bill, eob, estimate).findings


def run_audit(
    bill: DocumentSummary,
    eob: DocumentSummary | None = None,
    estimate: DocumentSummary | None = None,
) -> AuditResult:
    for doc, kind in ((bill, DocumentKind.bill), (eob, DocumentKind.eob), (estimate, DocumentKind.estimate)):
        if doc is not None and doc.kind != kind:
            raise ValueError(f"expected a {kind} document, got {doc.kind}")

    ids = _IdAllocator()
    limitations = list(BASE_LIMITATIONS)
    findings: list[Finding] = []
    findings += _check_bill_arithmetic(bill, ids, limitations)
    if eob is not None:
        findings += _check_insurance_comparison(bill, eob, ids, limitations)
    findings += _check_possible_duplicates(bill, eob, ids)
    findings += _check_missing_information(bill, eob, estimate, ids, limitations)
    return AuditResult(findings=findings, limitations=list(dict.fromkeys(limitations)))


def evidence_problems(findings: list[Finding], documents: list[DocumentSummary]) -> list[str]:
    """Invariant check: every evidence ref points at a real document, line, and page."""
    docs = {doc.id: doc for doc in documents}
    problems = []
    seen_ids = set()
    for finding in findings:
        if finding.id in seen_ids:
            problems.append(f"duplicate finding id {finding.id}")
        seen_ids.add(finding.id)
        for ref in finding.evidence:
            doc = docs.get(ref.document_id)
            if doc is None:
                problems.append(f"{finding.id}: unknown document {ref.document_id}")
                continue
            if ref.page is not None and ref.page > doc.pages:
                problems.append(f"{finding.id}: page {ref.page} beyond {doc.id} ({doc.pages} pages)")
            if ref.line_item_id is not None and ref.line_item_id not in {li.id for li in doc.line_items}:
                problems.append(f"{finding.id}: unknown line item {ref.line_item_id}")
    return problems


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_usd(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"


class _IdAllocator:
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def next(self, prefix: str) -> str:
        self._counts[prefix] += 1
        return f"f-{prefix}-{self._counts[prefix]}"


def _severity_for(difference_cents: int) -> FindingSeverity:
    if difference_cents >= MEDIUM_DIFFERENCE_CENTS:
        return FindingSeverity.medium
    return FindingSeverity.low


def _verification_note(doc: DocumentSummary, page: int | None, prefix: str = "Verify against") -> str:
    return f"{prefix} {doc.filename}" + (f", page {page}" if page else "")


def _document_field_ref(
    doc: DocumentSummary, field_name: str, amount: int | None, note: str | None = None
) -> EvidenceRef:
    # Document-level fields carry no page; a one-page document can only be page 1.
    page = 1 if doc.pages == 1 else None
    return EvidenceRef(
        document_id=doc.id,
        page=page,
        line_item_id=None,
        field=field_name,
        amount_cents=amount,
        source_text=None,
        verification_note=note or _verification_note(doc, page),
    )


def _line_ref(doc: DocumentSummary, index: int, item: LineItem, prefix: str = "Verify against") -> EvidenceRef:
    return EvidenceRef(
        document_id=doc.id,
        page=item.page,
        line_item_id=item.id,
        field=f"line_items[{index}].line_total_cents",
        amount_cents=item.line_total_cents,
        source_text=item.source_text,
        verification_note=_verification_note(doc, item.page, prefix),
    )


def _norm_id(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper()) if value else ""


def _norm_name(value: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split()) if value else ""


def _usable(doc: DocumentSummary | None) -> bool:
    return doc is not None and doc.extraction_quality != ExtractionQuality.failed


# ---------------------------------------------------------------------------
# R1: bill line items vs. total charges
# ---------------------------------------------------------------------------


def _check_bill_arithmetic(
    bill: DocumentSummary, ids: _IdAllocator, limitations: list[str]
) -> list[Finding]:
    if not _usable(bill):
        return []
    total = bill.total_charges_cents
    items = bill.line_items
    reason = None
    if total is None:
        reason = "the bill does not show total charges"
    elif not items:
        reason = "no individual charge lines were found"
    elif any(li.line_total_cents is None for li in items):
        reason = "some line amounts could not be read"
    elif any(li.line_total_cents < 0 for li in items):  # type: ignore[operator]
        reason = "credits or reversals are mixed into the charge lines, so the intended subtotal is unclear"
    if reason:
        limitations.append(f"The bill's line items were not checked against its total because {reason}.")
        return []

    line_sum = sum(li.line_total_cents for li in items)  # type: ignore[misc]
    if line_sum == total:
        return []

    difference = abs(line_sum - total)
    complete = bill.extraction_quality == ExtractionQuality.complete
    explanation = (
        f"The {len(items)} charge lines on the bill add up to {format_usd(line_sum)}, but the bill "
        f"lists total charges of {format_usd(total)}, a difference of {format_usd(difference)}. "
        "This is an inconsistency within the document itself; it does not by itself mean you "
        "were charged incorrectly."
    )
    if not complete:
        explanation += " Parts of this bill could not be read reliably, so a line may have been missed."
    alternatives = [
        "Some charge lines may be on a page that was not uploaded or could not be read.",
        "The total may include fees or earlier charges that are not itemized on this statement.",
    ]
    if line_sum > total:
        alternatives.append("A discount may already be reflected in the total charges.")

    return [
        Finding(
            id=ids.next("math"),
            rule_id=R1_BILL_TOTAL_ARITHMETIC,
            category=FindingCategory.arithmetic,
            status=FindingStatus.verified_inconsistency if complete else FindingStatus.needs_review,
            severity=_severity_for(difference),
            title="Bill line items do not add up to the total charges",
            explanation=explanation,
            alternative_explanations=alternatives,
            next_step="Ask the billing office for a complete itemized statement showing how the total charges were calculated.",
            difference_cents=difference,
            evidence=[_document_field_ref(bill, "total_charges_cents", total)]
            + [_line_ref(bill, i, li) for i, li in enumerate(items)],
            missing_information=[] if complete else ["A fully readable copy of every bill page"],
        )
    ]


# ---------------------------------------------------------------------------
# R2: bill amount due vs. EOB patient responsibility
# ---------------------------------------------------------------------------


def _eob_state(status: str | None) -> str:
    if not status:
        return "unknown"
    text = status.lower()
    if any(word in text for word in _PENDING_STATUS_WORDS):
        return "pending"
    if any(word in text for word in _FINAL_STATUS_WORDS):
        return "final"
    return "unknown"


def _match_claim(bill: DocumentSummary, eob: DocumentSummary) -> str:
    """'claim' (same claim number), 'visit' (same provider + date), 'conflict', or 'unknown'."""
    bill_claim, eob_claim = _norm_id(bill.claim_number), _norm_id(eob.claim_number)
    if bill_claim and eob_claim:
        return "claim" if bill_claim == eob_claim else "conflict"
    bill_provider, eob_provider = _norm_name(bill.provider_name), _norm_name(eob.provider_name)
    same_provider = bool(bill_provider and eob_provider) and (
        bill_provider == eob_provider or bill_provider in eob_provider or eob_provider in bill_provider
    )
    same_date = bill.service_date is not None and bill.service_date == eob.service_date
    return "visit" if same_provider and same_date else "unknown"


def _check_insurance_comparison(
    bill: DocumentSummary, eob: DocumentSummary, ids: _IdAllocator, limitations: list[str]
) -> list[Finding]:
    if not (_usable(bill) and _usable(eob)):
        return []  # R5 reports the unreadable document

    match = _match_claim(bill, eob)
    if match in ("conflict", "unknown"):
        limitations.append("The bill and EOB could not be matched to the same claim, so their amounts were not compared.")
        return [_unmatched_finding(bill, eob, match, ids)]

    state = _eob_state(eob.eob_status)
    if state == "pending":
        limitations.append("The EOB is not final, so its patient responsibility was not compared with the bill.")
        return [_pending_eob_finding(bill, eob, ids)]

    due, responsibility = bill.amount_due_cents, eob.patient_responsibility_cents
    if due is None or responsibility is None:
        limitations.append("The bill's amount due and the EOB's patient responsibility could not both be found, so they were not compared.")
        return [_missing_amounts_finding(bill, eob, ids)]
    if due == responsibility:
        return []

    difference = abs(due - responsibility)
    claim = bill.claim_number or eob.claim_number
    service_date = bill.service_date or eob.service_date
    if match == "claim":
        lead = f"For matching Claim {claim}"
    else:
        lead = "For what appears to be the same visit (same provider and service date)"
    if service_date:
        lead += f" (service date {service_date})"
    eob_label = f"the {eob.eob_status.lower()} EOB" if state == "final" and eob.eob_status else "the EOB"
    explanation = (
        f"{lead}, the provider statement shows a current balance due of {format_usd(due)}, while "
        f"{eob_label} lists {format_usd(responsibility)} in patient responsibility. This "
        f"{format_usd(difference)} difference warrants clarification; it does not prove an improper charge."
    )

    if due > responsibility:
        eob_dated = f" (dated {eob.document_date})" if eob.document_date else ""
        bill_dated = f" (dated {bill.document_date})" if bill.document_date else ""
        alternatives = [
            f"An insurance payment or contractual adjustment on the EOB{eob_dated} may not yet be "
            f"posted to the provider statement{bill_dated}.",
            "The provider statement balance may include prior balances or services from a separate claim.",
        ]
        claim_part = f" for Claim {claim}" if claim else ""
        next_step = (
            "Ask the provider billing office for an updated itemized account statement that "
            f"reconciles the {format_usd(due)} balance with {eob_label}{claim_part}."
        )
    else:
        alternatives = [
            "A payment you already made (for example, a copay at the visit) may have been applied to the statement.",
            "The claim may have been reprocessed after the EOB was issued.",
        ]
        next_step = (
            "Ask the provider billing office to confirm which payments and adjustments have been "
            "applied to your account, and keep the EOB for your records."
        )

    missing = []
    if match == "visit":
        missing.append("A claim number shown on both documents to confirm they are the same claim")
    if state == "unknown":
        missing.append("A final claim status on the EOB")

    return [
        Finding(
            id=ids.next("eob"),
            rule_id=R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
            category=FindingCategory.insurance_comparison,
            status=FindingStatus.needs_review,
            severity=_severity_for(difference),
            title="Statement amount due and EOB patient responsibility differ",
            explanation=explanation,
            alternative_explanations=alternatives,
            next_step=next_step,
            difference_cents=difference,
            evidence=[
                _document_field_ref(bill, "amount_due_cents", due),
                _document_field_ref(eob, "patient_responsibility_cents", responsibility),
            ],
            missing_information=missing,
        )
    ]


def _claim_refs(bill: DocumentSummary, eob: DocumentSummary) -> list[EvidenceRef]:
    refs = []
    for doc in (bill, eob):
        note = (
            f"Claim number shown: {doc.claim_number}"
            if doc.claim_number
            else f"No claim number found in {doc.filename}"
        )
        refs.append(_document_field_ref(doc, "claim_number", None, note))
    return refs


def _unmatched_finding(
    bill: DocumentSummary, eob: DocumentSummary, match: str, ids: _IdAllocator
) -> Finding:
    if match == "conflict":
        explanation = (
            f"The bill shows claim number {bill.claim_number} but the EOB shows {eob.claim_number}, "
            "so ClearBill did not compare their amounts. They may describe different visits or claims."
        )
    else:
        explanation = (
            "The bill and EOB do not share a claim number, and their provider and service date do "
            "not clearly match, so ClearBill did not compare their amounts."
        )
    return Finding(
        id=ids.next("eob"),
        rule_id=R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
        category=FindingCategory.insurance_comparison,
        status=FindingStatus.insufficient_information,
        severity=FindingSeverity.info,
        title="Bill and EOB could not be matched to the same claim",
        explanation=explanation,
        alternative_explanations=[
            "The EOB may be for a different visit or a different claim from the same provider.",
            "One document may show an account number instead of the insurer's claim number.",
        ],
        next_step=(
            "Check that the EOB is for the same visit as the bill (same provider and date of "
            "service). If it is, ask the billing office which claim the statement balance belongs to."
        ),
        difference_cents=None,
        evidence=_claim_refs(bill, eob),
        missing_information=["A claim number, provider, and service date that match on both documents"],
    )


def _pending_eob_finding(bill: DocumentSummary, eob: DocumentSummary, ids: _IdAllocator) -> Finding:
    evidence = [_document_field_ref(eob, "eob_status", None, f"Claim status shown: {eob.eob_status}")]
    if eob.patient_responsibility_cents is not None:
        evidence.append(_document_field_ref(eob, "patient_responsibility_cents", eob.patient_responsibility_cents))
    if bill.amount_due_cents is not None:
        evidence.append(_document_field_ref(bill, "amount_due_cents", bill.amount_due_cents))
    return Finding(
        id=ids.next("eob"),
        rule_id=R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
        category=FindingCategory.insurance_comparison,
        status=FindingStatus.insufficient_information,
        severity=FindingSeverity.info,
        title="EOB is not final yet",
        explanation=(
            f'The EOB lists the claim status as "{eob.eob_status}", so the patient responsibility may '
            "still change. ClearBill did not treat any difference from the bill as a discrepancy."
        ),
        alternative_explanations=[
            "Insurers often update the patient responsibility once a claim finishes processing.",
        ],
        next_step=(
            "Wait for the finalized EOB, or ask your insurer when the claim will finish processing, "
            "before comparing it with the bill."
        ),
        difference_cents=None,
        evidence=evidence,
        missing_information=["A finalized EOB for this claim"],
    )


def _missing_amounts_finding(bill: DocumentSummary, eob: DocumentSummary, ids: _IdAllocator) -> Finding:
    missing = []
    evidence = []
    if bill.amount_due_cents is None:
        missing.append("The current balance or amount due on the bill")
    else:
        evidence.append(_document_field_ref(bill, "amount_due_cents", bill.amount_due_cents))
    if eob.patient_responsibility_cents is None:
        missing.append("The patient responsibility amount on the EOB")
    else:
        evidence.append(_document_field_ref(eob, "patient_responsibility_cents", eob.patient_responsibility_cents))
    return Finding(
        id=ids.next("eob"),
        rule_id=R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
        category=FindingCategory.insurance_comparison,
        status=FindingStatus.insufficient_information,
        severity=FindingSeverity.info,
        title="Bill and EOB amounts could not be compared",
        explanation=(
            "ClearBill could not find "
            + " or ".join(m[0].lower() + m[1:] for m in missing)
            + ", so the amount you are asked to pay could not be compared with the amount your "
            "insurer says you owe."
        ),
        alternative_explanations=["The amount may be printed in a part of the document that could not be read."],
        next_step="Check the original documents for these amounts. If one is missing, ask the provider or insurer for a statement that shows it.",
        difference_cents=None,
        evidence=evidence,
        missing_information=missing,
    )


# ---------------------------------------------------------------------------
# R3: possible duplicate line items on the bill
# ---------------------------------------------------------------------------


def _line_identity(item: LineItem) -> tuple[str, str] | None:
    if item.code and _norm_id(item.code):
        return ("code", _norm_id(item.code))
    description = _norm_name(item.description)
    if description and description != "description not legible":
        return ("description", description)
    return None


def _check_possible_duplicates(
    bill: DocumentSummary, eob: DocumentSummary | None, ids: _IdAllocator
) -> list[Finding]:
    if not _usable(bill):
        return []
    groups: dict[tuple, list[tuple[int, LineItem]]] = defaultdict(list)
    reversals: set[tuple] = set()
    for index, item in enumerate(bill.line_items):
        amount = item.line_total_cents
        identity = _line_identity(item)
        if amount is None or amount == 0 or identity is None:
            continue
        service_date = item.service_date or bill.service_date
        if amount < 0:
            reversals.add((identity, service_date, -amount))
            continue
        groups[(identity, service_date, amount, item.quantity)].append((index, item))

    eob_codes: list[str] | None = None
    if _usable(eob):
        eob_codes = [_norm_id(li.code) for li in eob.line_items if li.code]  # type: ignore[union-attr]

    findings = []
    for (identity, service_date, amount, _quantity), members in groups.items():
        if len(members) < 2 or (identity, service_date, amount) in reversals:
            continue
        count = len(members)
        first = members[0][1]
        description = first.description
        code = first.code if identity[0] == "code" else None
        label = f"Code {code} ({description})" if code else f'"{description}"'
        on_date = f" on {service_date}" if service_date else ""
        explanation = (
            f"{label} appears {_TIMES.get(count, f'{count} times')}{on_date} for "
            f"{format_usd(amount)} each on the provider bill"
        )
        severity = FindingSeverity.low
        if code and eob_codes:
            eob_count = eob_codes.count(identity[1])
            if eob_count >= count:
                severity = FindingSeverity.info
                explanation += (
                    f". The EOB also lists it {_TIMES.get(eob_count, f'{eob_count} times')}, which "
                    "suggests the insurer processed each entry as a separate service"
                )
            elif eob_count == 0:
                explanation += ", but it does not appear on the EOB"
            else:
                explanation += f", whereas it appears {_TIMES.get(eob_count, f'{eob_count} times')} on the EOB"
        explanation += (
            ". Repeated entries can be legitimate, so this is a question to ask, not proof of a duplicate charge."
        )
        findings.append(
            Finding(
                id=ids.next("dup"),
                rule_id=R3_POSSIBLE_DUPLICATE_LINE_ITEM,
                category=FindingCategory.possible_duplicate,
                status=FindingStatus.needs_review,
                severity=severity,
                title="Possible repeat line item on same service date",
                explanation=explanation,
                alternative_explanations=[
                    "Separate services of the same type may have been performed during the visit.",
                    "Separate facility and professional (or lab processing) charges may be listed under similar descriptions.",
                ],
                next_step=(
                    f'Ask the billing office to confirm whether {count} separate "{description}" '
                    f"services were provided{on_date}, or whether one of the entries is a duplicate."
                ),
                difference_cents=amount * (count - 1),
                evidence=[
                    _line_ref(
                        bill,
                        index,
                        item,
                        prefix=f"{_ORDINALS[n] if n < len(_ORDINALS) else f'Instance {n + 1}'} instance on",
                    )
                    for n, (index, item) in enumerate(members)
                ],
                missing_information=[],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# R5: missing information
# ---------------------------------------------------------------------------

_KIND_LABELS = {
    DocumentKind.bill: "provider bill",
    DocumentKind.eob: "EOB",
    DocumentKind.estimate: "Good Faith Estimate",
}


def _check_missing_information(
    bill: DocumentSummary,
    eob: DocumentSummary | None,
    estimate: DocumentSummary | None,
    ids: _IdAllocator,
    limitations: list[str],
) -> list[Finding]:
    findings = []
    for doc in (bill, eob, estimate):
        if doc is None:
            continue
        label = _KIND_LABELS[doc.kind]
        if doc.extraction_quality == ExtractionQuality.failed:
            findings.append(
                Finding(
                    id=ids.next("missing"),
                    rule_id=R5_MISSING_INFORMATION,
                    category=FindingCategory.missing_context,
                    status=FindingStatus.insufficient_information,
                    severity=FindingSeverity.info,
                    title=f"The {label} could not be read",
                    explanation=(
                        f"ClearBill could not extract billing amounts from {doc.filename}, so checks "
                        "that depend on it were skipped."
                    ),
                    alternative_explanations=[
                        "The file may be blurry, cropped, handwritten, or not a billing document.",
                    ],
                    next_step="Try uploading a clearer PDF or photo of the full document, or compare the amounts by hand.",
                    difference_cents=None,
                    evidence=[
                        EvidenceRef(
                            document_id=doc.id,
                            field="extraction_quality",
                            verification_note=f"Review {doc.filename}",
                        )
                    ],
                    missing_information=doc.extraction_warnings[:3],
                )
            )
            limitations.append(f"The {label} could not be read, so checks that depend on it were skipped.")
        elif doc.extraction_quality == ExtractionQuality.partial:
            limitations.append(
                f"Some values in the {label} ({doc.filename}) could not be read reliably; checks that rely on them may be incomplete."
            )

    if eob is None:
        findings.append(
            Finding(
                id=ids.next("missing"),
                rule_id=R5_MISSING_INFORMATION,
                category=FindingCategory.missing_context,
                status=FindingStatus.insufficient_information,
                severity=FindingSeverity.info,
                title="Insurance comparison not available",
                explanation=(
                    "No Explanation of Benefits (EOB) was uploaded, so ClearBill could not compare the "
                    "bill with how your insurance processed the claim. Bill-only checks were still run."
                ),
                alternative_explanations=[
                    "If the visit was self-pay or not billed to insurance, there may be no EOB.",
                ],
                next_step=(
                    "If you have insurance, find the EOB for this visit in your insurer's member portal "
                    "or mail and upload it together with the bill."
                ),
                difference_cents=None,
                evidence=[],
                missing_information=["Explanation of Benefits (EOB) for this visit"],
            )
        )
        limitations.append("No EOB was provided, so the bill could not be compared with how insurance processed the claim.")

    if estimate is not None:
        limitations.append(
            "Good Faith Estimate comparison is not supported in this version; the estimate was read but not compared with the bill."
        )
    return findings
