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
    R6_GFE_PATIENT_AMOUNT_THRESHOLD       bill amount due vs. GFE ($400 review trigger)
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
R6_GFE_PATIENT_AMOUNT_THRESHOLD = "R6_GFE_PATIENT_AMOUNT_THRESHOLD"
R5_MISSING_INFORMATION = "R5_MISSING_INFORMATION"

# Differences at or above this many cents are "medium" severity; smaller ones "low".
MEDIUM_DIFFERENCE_CENTS = 5000

BASE_LIMITATIONS = [
    "Sana runs a limited set of automated checks (bill arithmetic, bill vs. EOB "
    "and GFE comparison, possible repeated charges, and coded-price references). A flagged difference is a reason to ask "
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
    if estimate is not None:
        findings += _check_gfe_comparison(bill, estimate, ids, limitations)
    findings += _check_possible_duplicates(bill, eob, ids)
    findings += _check_missing_information(bill, eob, estimate, ids, limitations)
    return AuditResult(findings=findings, limitations=list(dict.fromkeys(limitations)))


GFE_REVIEW_THRESHOLD_CENTS = 40_000


def _check_gfe_comparison(
    bill: DocumentSummary,
    estimate: DocumentSummary,
    ids: _IdAllocator,
    limitations: list[str],
) -> list[Finding]:
    """Compare the patient balance to the GFE and flag a $400-or-more increase."""
    if not (_usable(bill) and _usable(estimate)):
        return []  # R5 reports an unreadable document.

    mismatches = []
    bill_provider, estimate_provider = _norm_name(bill.provider_name), _norm_name(estimate.provider_name)
    if bill_provider and estimate_provider and not (
        bill_provider == estimate_provider
        or bill_provider in estimate_provider
        or estimate_provider in bill_provider
    ):
        mismatches.append("provider/facility names differ")
    if bill.service_date and estimate.service_date and bill.service_date != estimate.service_date:
        mismatches.append("service dates differ")
    if mismatches:
        limitations.append("The bill and Good Faith Estimate were not compared because their " + " and ".join(mismatches) + ".")
        return [Finding(
            id=ids.next("gfe"), rule_id=R6_GFE_PATIENT_AMOUNT_THRESHOLD,
            category=FindingCategory.estimate_comparison,
            status=FindingStatus.insufficient_information, severity=FindingSeverity.info,
            title="Bill and Good Faith Estimate may describe different care",
            explanation="Sana did not compare the amounts because the provider/facility or service date does not match clearly.",
            alternative_explanations=["The estimate may cover a different provider, facility, or service date."],
            next_step="Confirm that this estimate and bill are for the same provider or facility and the same scheduled service.",
            difference_cents=None,
            evidence=[_document_field_ref(bill, "provider_name", None), _document_field_ref(estimate, "provider_name", None)],
            missing_information=["A Good Faith Estimate for the same provider/facility and service"],
        )]

    due, expected = bill.amount_due_cents, estimate.expected_total_cents
    if due is None or expected is None:
        missing = []
        evidence = []
        if due is None:
            missing.append("The current patient balance due on the bill")
        else:
            evidence.append(_document_field_ref(bill, "amount_due_cents", due))
        if expected is None:
            missing.append("The total expected patient cost on the Good Faith Estimate")
        else:
            evidence.append(_document_field_ref(estimate, "expected_total_cents", expected))
        limitations.append("The bill and Good Faith Estimate could not be compared because one or both patient amounts were unavailable.")
        return [Finding(
            id=ids.next("gfe"), rule_id=R6_GFE_PATIENT_AMOUNT_THRESHOLD,
            category=FindingCategory.estimate_comparison,
            status=FindingStatus.insufficient_information, severity=FindingSeverity.info,
            title="Good Faith Estimate comparison needs more information",
            explanation="Sana could not compare the bill's current patient balance with the estimate's expected patient cost.",
            alternative_explanations=["The relevant amount may not be printed or may not have been read reliably."],
            next_step="Check the original bill and estimate for the current patient balance and total expected patient cost.",
            difference_cents=None, evidence=evidence, missing_information=missing,
        )]

    difference = due - expected
    if difference <= 0:
        return []
    threshold_met = difference >= GFE_REVIEW_THRESHOLD_CENTS
    complete = bill.extraction_quality == estimate.extraction_quality == ExtractionQuality.complete
    findings = Finding(
        id=ids.next("gfe"), rule_id=R6_GFE_PATIENT_AMOUNT_THRESHOLD,
        category=FindingCategory.estimate_comparison,
        status=FindingStatus.needs_review,
        severity=FindingSeverity.medium if threshold_met else FindingSeverity.info,
        title=("Patient balance is at least $400 above the Good Faith Estimate" if threshold_met
               else "Patient balance is above the Good Faith Estimate"),
        explanation=(
            f"The bill lists a current patient balance of {format_usd(due)} and the Good Faith Estimate "
            f"lists expected patient costs of {format_usd(expected)}, a difference of {format_usd(difference)}. "
            + ("This meets Sana's $400 patient-balance review trigger and may warrant checking the Patient-Provider Dispute Resolution process. CMS eligibility is based on charges for the same provider/facility and has additional requirements; this comparison does not determine eligibility. "
               if threshold_met else "This is below Sana's $400 patient-balance review trigger. ")
            + "Verify both amounts and confirm they cover the same provider/facility and service."
            + (" The extraction was partial, so check the original documents." if not complete else "")
        ),
        alternative_explanations=[
            "The estimate or bill may include a different set of services, providers, or facilities.",
            "The patient balance may include payments, adjustments, or other charges not reflected in the estimate total.",
        ],
        next_step=(
            "Ask the provider or facility to reconcile the bill with the estimate. For a possible PPDR request, check CMS eligibility and the 120-day filing deadline at cms.gov/initiatives/your-patient-rights/medical-bill-rights/get-help/dispute-bill."
            if threshold_met else "Ask the provider to explain the difference and confirm that both documents cover the same services."
        ),
        difference_cents=difference,
        evidence=[
            _document_field_ref(bill, "amount_due_cents", due),
            _document_field_ref(estimate, "expected_total_cents", expected),
        ],
        missing_information=(
            ["Whether you were uninsured or chose not to use insurance for this care", "Whether the estimate was provided at least 3 days before scheduled care", "Whether this is an initial bill received within the 120-day filing period", "Whether the bill and estimate cover the same provider/facility and services"]
            if threshold_met else []
        ),
    )
    return [findings]


def price_benchmark_findings(
    bill: DocumentSummary, averages: dict[str, tuple[int, str]]
) -> list[Finding]:
    """Create review prompts for billed coded services far above the CMS baseline."""
    findings = []
    for index, item in enumerate(bill.line_items):
        if not item.code or item.line_total_cents is None or item.line_total_cents <= 0:
            continue
        if item.quantity != 1:
            continue
        charge_cents = item.unit_amount_cents if item.unit_amount_cents is not None else item.line_total_cents
        reference = averages.get(item.code.upper())
        if reference is None:
            continue
        average_cents, year = reference
        if charge_cents <= average_cents * 1.5:
            continue
        ratio = charge_cents / average_cents
        findings.append(Finding(
            id=f"f-price-{len(findings) + 1}",
            rule_id="R4_CMS_NATIONAL_PRICE_REFERENCE",
            category=FindingCategory.price_benchmark,
            status=FindingStatus.needs_review,
            severity=FindingSeverity.medium,
            title="Coded charge is well above the CMS national reference",
            explanation=(
                f'Code {item.code} is billed at {format_usd(charge_cents)} per unit, '
                f'about {ratio:.1f} times the {year} CMS national average submitted charge of '
                f'{format_usd(average_cents)} for the same code. This benchmark covers Original '
                "Medicare Part B claims and is a prompt to ask questions, not proof of an error. "
                "The national figure blends CMS facility and non-facility service averages; your "
                "care setting is not reliably identified here, and commercial, self-pay, hospital, "
                "and negotiated prices can differ."
            ),
            alternative_explanations=[
                "The line may include modifiers, multiple units, or components not reflected by the code alone.",
                "Medicare submitted charges may not represent prices for this provider, insurance plan, or care setting.",
            ],
            next_step="Ask the provider for the code, units, care setting, and pricing basis, then compare it with your plan's allowed amount or a matching local estimate.",
            difference_cents=None,
            evidence=[_line_ref(bill, index, item, prefix=f"Compare with CMS {year} national reference; verify against")],
            missing_information=["Whether this service and care setting match the Medicare reference"],
        ))
    return findings


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


def _check_unit_arithmetic(
    bill: DocumentSummary, items: list[LineItem], ids: _IdAllocator
) -> list[Finding]:
    findings = []
    for index, item in enumerate(items):
        if (item.quantity is None or item.unit_amount_cents is None
                or item.line_total_cents is None or item.line_total_cents < 0):
            continue
        expected = item.quantity * item.unit_amount_cents
        if expected == item.line_total_cents:
            continue
        difference = abs(expected - item.line_total_cents)
        complete = bill.extraction_quality == ExtractionQuality.complete
        findings.append(Finding(
            id=ids.next("math"), rule_id=R1_BILL_TOTAL_ARITHMETIC,
            category=FindingCategory.arithmetic,
            status=FindingStatus.verified_inconsistency if complete else FindingStatus.needs_review,
            severity=_severity_for(difference),
            title="A line item's unit price and quantity do not match its total",
            explanation=(
                f'"{item.description}" lists {item.quantity} × {format_usd(item.unit_amount_cents)} '
                f'but shows a line total of {format_usd(item.line_total_cents)}. The arithmetic '
                f'difference is {format_usd(difference)}; verify the printed figures.'
                + (" The extraction was partial, so this needs manual review." if not complete else "")
            ),
            alternative_explanations=[
                "The quantity or unit amount may have been misread during extraction.",
                "The displayed line total may include a modifier, discount, or other adjustment.",
            ],
            next_step="Ask the billing office to explain how this line total was calculated.",
            difference_cents=difference, evidence=[_line_ref(bill, index, item)],
            missing_information=[] if complete else ["A fully readable copy of this bill line"],
        ))
    return findings


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
        return _check_unit_arithmetic(bill, items, ids)

    findings: list[Finding] = []
    # Check each line's own multiplication before reconciling the statement total.
    # A missing unit price or quantity means we cannot verify that line.
    for index, item in enumerate(items):
        if (item.quantity is None or item.unit_amount_cents is None
                or item.line_total_cents is None or item.line_total_cents < 0):
            continue
        expected = item.quantity * item.unit_amount_cents
        if expected == item.line_total_cents:
            continue
        difference = abs(expected - item.line_total_cents)
        complete = bill.extraction_quality == ExtractionQuality.complete
        findings.append(Finding(
            id=ids.next("math"),
            rule_id=R1_BILL_TOTAL_ARITHMETIC,
            category=FindingCategory.arithmetic,
            status=FindingStatus.verified_inconsistency if complete else FindingStatus.needs_review,
            severity=_severity_for(difference),
            title="A line item's unit price and quantity do not match its total",
            explanation=(
                f'"{item.description}" lists {item.quantity} × {format_usd(item.unit_amount_cents)} '
                f'but shows a line total of {format_usd(item.line_total_cents)}. The arithmetic '
                f'difference is {format_usd(difference)}; verify the printed figures.'
                + (" The extraction was partial, so this needs manual review." if not complete else "")
            ),
            alternative_explanations=[
                "The quantity or unit amount may have been misread during extraction.",
                "The displayed line total may include a modifier, discount, or other adjustment.",
            ],
            next_step="Ask the billing office to explain how this line total was calculated.",
            difference_cents=difference,
            evidence=[_line_ref(bill, index, item)],
            missing_information=[] if complete else ["A fully readable copy of this bill line"],
        ))

    line_sum = sum(li.line_total_cents for li in items)  # type: ignore[misc]
    if line_sum == total:
        return findings

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

    return findings + [
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
    """Match by claim ID or provider/date while preserving conflicting-ID context."""
    bill_claim, eob_claim = _norm_id(bill.claim_number), _norm_id(eob.claim_number)
    bill_provider, eob_provider = _norm_name(bill.provider_name), _norm_name(eob.provider_name)
    same_provider = bool(bill_provider and eob_provider) and (
        bill_provider == eob_provider or bill_provider in eob_provider or eob_provider in bill_provider
    )
    same_date = bill.service_date is not None and bill.service_date == eob.service_date
    same_visit = same_provider and same_date
    if bill_claim and eob_claim:
        if bill_claim == eob_claim:
            return "claim"
        # EOBs and provider statements may label different identifiers as the
        # claim number. Compare provisionally only when provider and date agree.
        return "visit_conflict" if same_visit else "conflict"
    return "visit" if same_visit else "unknown"


def _check_insurance_comparison(
    bill: DocumentSummary, eob: DocumentSummary, ids: _IdAllocator, limitations: list[str]
) -> list[Finding]:
    if not (_usable(bill) and _usable(eob)):
        return []  # R5 reports the unreadable document

    match = _match_claim(bill, eob)
    match_unverified = match in ("conflict", "unknown")

    state = _eob_state(eob.eob_status)
    if state == "pending":
        limitations.append("The EOB is not final, so its patient responsibility was not compared with the bill.")
        return [_pending_eob_finding(bill, eob, ids)]

    due, responsibility = bill.amount_due_cents, eob.patient_responsibility_cents
    if due is None or responsibility is None:
        limitations.append("The bill's amount due and the EOB's patient responsibility could not both be found, so they were not compared.")
        finding = _missing_amounts_finding(bill, eob, ids)
        if match_unverified:
            finding.explanation += (
                " The claim match is also unverified; compare the extracted identifiers below "
                "with the documents."
            )
            finding.missing_information.append(
                "Confirmation that the uploaded bill and EOB refer to the same claim or visit"
            )
            finding.evidence.extend(_claim_refs(bill, eob))
        return [finding]
    if due == responsibility:
        if match_unverified:
            return [_unverified_equal_amounts_finding(bill, eob, due, responsibility, ids)]
        return []

    difference = abs(due - responsibility)
    claim = bill.claim_number or eob.claim_number
    service_date = bill.service_date or eob.service_date
    if match == "claim":
        lead = f"For matching Claim {claim}"
    elif match == "visit_conflict":
        lead = "For the same provider and service date, although the printed claim identifiers differ"
    elif match_unverified:
        lead = "For the uploaded bill and EOB pair (claim match not verified)"
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
    if match == "visit_conflict":
        explanation += (
            f" The bill lists identifier {bill.claim_number}; the EOB lists {eob.claim_number}."
        )
    elif match_unverified:
        explanation += (
            " Sana could not verify that the documents cover the same claim, so treat this "
            "amount difference as a preliminary comparison until the provider or insurer confirms the match."
        )

    if due > responsibility:
        eob_dated = f" (dated {eob.document_date})" if eob.document_date else ""
        bill_dated = f" (dated {bill.document_date})" if bill.document_date else ""
        alternatives = [
            f"An insurance payment or contractual adjustment on the EOB{eob_dated} may not yet be "
            f"posted to the provider statement{bill_dated}.",
            "The provider statement balance may include prior balances or services from a separate claim.",
        ]
        if match_unverified:
            alternatives.append(
                "The EOB may refer to a different claim; confirm the match before acting on this comparison."
            )
        if match_unverified:
            next_step = (
                "Ask the provider or insurer to confirm that the uploaded EOB covers this bill, then "
                "request an updated itemized statement reconciling the amounts."
            )
        elif match == "visit_conflict":
            alternatives.append(
                "The two documents may use different claim or account identifiers for the same visit."
            )
            next_step = (
                "Ask the provider or insurer to confirm that the differing identifiers refer to "
                "the same claim, then request an updated itemized statement reconciling the "
                f"{format_usd(due)} balance with {eob_label}."
            )
        else:
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
    elif match == "visit_conflict":
        missing.append(
            f"Confirmation that bill identifier {bill.claim_number} and EOB identifier "
            f"{eob.claim_number} refer to the same claim"
        )
    elif match_unverified:
        missing.append("Confirmation that the uploaded bill and EOB refer to the same claim or visit")
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


def _unverified_equal_amounts_finding(
    bill: DocumentSummary,
    eob: DocumentSummary,
    due: int,
    responsibility: int,
    ids: _IdAllocator,
) -> Finding:
    """Report equal uploaded amounts without claiming the documents are matched."""
    return Finding(
        id=ids.next("eob"),
        rule_id=R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
        category=FindingCategory.insurance_comparison,
        status=FindingStatus.insufficient_information,
        severity=FindingSeverity.info,
        title="Patient amounts match, but the claim match needs confirmation",
        explanation=(
            f"The bill and uploaded EOB both show {format_usd(due)} as the patient amount. "
            "Sana could not verify that they cover the same claim, so confirm the match "
            "before treating the amounts as reconciled."
        ),
        alternative_explanations=[],
        next_step="Ask the provider or insurer to confirm that this EOB belongs to the uploaded bill.",
        difference_cents=abs(due - responsibility),
        evidence=[
            _document_field_ref(bill, "amount_due_cents", due),
            _document_field_ref(eob, "patient_responsibility_cents", responsibility),
        ],
        missing_information=["Confirmation that the uploaded bill and EOB refer to the same claim or visit"],
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
            "still change. Sana did not treat any difference from the bill as a discrepancy."
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
            "Sana could not find "
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
                        f"Sana could not extract billing amounts from {doc.filename}, so checks "
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
                    "No readable Explanation of Benefits (EOB) was available, so Sana could not "
                    "compare the bill with how your insurance processed the claim. Other available checks were still run."
                ),
                alternative_explanations=[
                    "If the visit was self-pay or not billed to insurance, there may be no EOB.",
                ],
                next_step=(
                    "If you have insurance, make sure the EOB for this visit is readable and upload it "
                    "together with the bill. You can also check it in your insurer's member portal or mail."
                ),
                difference_cents=None,
                evidence=[],
                missing_information=["Explanation of Benefits (EOB) for this visit"],
            )
        )
        limitations.append("No readable EOB was available, so the bill could not be compared with how insurance processed the claim.")

    return findings
