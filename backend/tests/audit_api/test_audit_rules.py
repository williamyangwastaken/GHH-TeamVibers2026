"""Deterministic audit rules, organized by the handoff's section 12 scenarios."""

import re

import pytest

from app.schemas import AnalysisResponse, FindingSeverity, FindingStatus
from app.services.audit import (
    BASE_LIMITATIONS,
    R1_BILL_TOTAL_ARITHMETIC,
    R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH,
    R3_POSSIBLE_DUPLICATE_LINE_ITEM,
    R6_GFE_PATIENT_AMOUNT_THRESHOLD,
    R5_MISSING_INFORMATION,
    evidence_problems,
    format_usd,
    run_audit,
)
from app.services.case_store import load_demo_case
from audit_cases import clean_bill, clean_eob, demo_documents, estimate_doc, line

ACCUSATORY = re.compile(r"\b(fraud\w*|illegal\w*|overcharg\w*|scam\w*|guarantee\w*)\b", re.I)


def rules(result):
    return [(f.rule_id, f.status) for f in result.findings]


def assert_sound(result, *docs):
    """Invariants every audit must satisfy, whatever the scenario."""
    docs = [d for d in docs if d is not None]
    assert evidence_problems(result.findings, docs) == []
    AnalysisResponse(
        case_id="t", is_demo=False, documents=docs, findings=result.findings,
        limitations=result.limitations, safety_disclaimer="x",
    )
    for f in result.findings:
        text = " ".join([f.title, f.explanation, f.next_step, *f.alternative_explanations])
        assert not ACCUSATORY.search(text), text
        assert f.difference_cents is None or f.difference_cents > 0


# --- demo-mismatch ----------------------------------------------------------


def test_demo_mismatch_reproduces_fixture_findings():
    case = load_demo_case()
    bill, eob = demo_documents()
    result = run_audit(bill, eob)

    def signature(f):
        return (
            f.id, f.rule_id, f.category, f.status, f.severity, f.difference_cents,
            [(e.document_id, e.line_item_id, e.field, e.amount_cents, e.page) for e in f.evidence],
        )

    assert [signature(f) for f in result.findings] == [signature(f) for f in case.findings]
    assert result.findings[0].explanation == case.findings[0].explanation
    assert_sound(result, bill, eob)


def test_demo_r2_is_needs_review_never_a_savings_claim():
    bill, eob = demo_documents()
    r2 = run_audit(bill, eob).findings[0]
    assert (r2.status, r2.severity, r2.difference_cents) == (FindingStatus.needs_review, FindingSeverity.medium, 25000)
    assert "does not prove" in r2.explanation


# --- bill-only --------------------------------------------------------------


def test_bill_only_states_insurance_comparison_unavailable():
    bill = clean_bill()
    result = run_audit(bill)
    assert rules(result) == [(R5_MISSING_INFORMATION, FindingStatus.insufficient_information)]
    assert result.findings[0].title == "Insurance comparison not available"
    assert result.findings[0].evidence == []
    assert any("No readable EOB was available" in lim for lim in result.limitations)
    assert_sound(result, bill)


def test_bill_only_still_runs_bill_checks():
    bill = clean_bill(
        total_charges_cents=92000,
        line_items=[
            line("li_1", "Visit", 52000, code="99214"),
            line("li_2", "Lab draw", 20000, code="36415"),
            line("li_3", "Lab draw", 20000, code="36415"),
        ],
    )
    result = run_audit(bill)
    assert [f.rule_id for f in result.findings] == [R3_POSSIBLE_DUPLICATE_LINE_ITEM, R5_MISSING_INFORMATION]
    assert_sound(result, bill)


# --- clean-matched ----------------------------------------------------------


def test_clean_matched_documents_have_no_findings():
    bill, eob = clean_bill(), clean_eob()
    result = run_audit(bill, eob)
    assert result.findings == []
    assert result.limitations == BASE_LIMITATIONS


# --- possible-duplicate / legitimate-repeat ---------------------------------


def test_possible_duplicate_is_flagged_as_a_question():
    bill = clean_bill(
        total_charges_cents=92000,
        line_items=[*clean_bill().line_items, line("li_bill_3", "Venipuncture", 20000, code="36415")],
    )
    result = run_audit(bill, clean_eob(amount_due_cents=39000))
    (dup,) = [f for f in result.findings if f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM]
    assert (dup.status, dup.severity, dup.difference_cents) == (FindingStatus.needs_review, FindingSeverity.low, 20000)
    assert [e.line_item_id for e in dup.evidence] == ["li_bill_2", "li_bill_3"]
    assert "appears once on the EOB" in dup.explanation
    assert len(dup.alternative_explanations) >= 2
    assert_sound(result, bill, clean_eob())


def test_three_repeats_count_each_extra_copy():
    bill = clean_bill(
        total_charges_cents=None,
        line_items=[line(f"li_{i}", "Lab draw", 1500, code="36415") for i in range(3)],
    )
    (dup,) = [f for f in run_audit(bill).findings if f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM]
    assert dup.difference_cents == 3000
    assert "three times" in dup.explanation


@pytest.mark.parametrize(
    "second",
    [
        line("li_2", "Venipuncture", 20000, code="36415", qty=2),  # different quantity
        line("li_2", "Venipuncture", 25000, code="36415"),  # different amount
        line("li_2", "Venipuncture", 20000, code="36415", date="2026-10-02"),  # different day
        line("li_2", "Venipuncture", 20000, code="36416"),  # different service
    ],
    ids=["quantity", "amount", "date", "code"],
)
def test_legitimate_repeats_are_not_called_duplicates(second):
    bill = clean_bill(total_charges_cents=None, line_items=[line("li_1", "Venipuncture", 20000, code="36415"), second])
    assert not any(f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM for f in run_audit(bill).findings)


def test_reversed_repeat_is_not_flagged():
    bill = clean_bill(
        total_charges_cents=None,
        line_items=[
            line("li_1", "Venipuncture", 20000, code="36415"),
            line("li_2", "Venipuncture", 20000, code="36415"),
            line("li_3", "Venipuncture reversal", -20000, code="36415"),
        ],
    )
    assert not any(f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM for f in run_audit(bill).findings)


def test_repeat_also_on_eob_is_informational():
    repeated = [line("li_1", "Venipuncture", 20000, code="36415"), line("li_2", "Venipuncture", 20000, code="36415")]
    bill = clean_bill(total_charges_cents=40000, amount_due_cents=None, line_items=repeated)
    eob = clean_eob(line_items=[line("e1", "Venipuncture", 20000, code="36415"), line("e2", "Venipuncture", 20000, code="36415")])
    (dup,) = [f for f in run_audit(bill, eob).findings if f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM]
    assert dup.severity == FindingSeverity.info
    assert "EOB also lists it twice" in dup.explanation


def test_duplicates_match_on_description_when_no_code():
    bill = clean_bill(
        total_charges_cents=None,
        line_items=[line("li_1", "Facility Fee", 9900), line("li_2", "facility  fee", 9900)],
    )
    assert any(f.rule_id == R3_POSSIBLE_DUPLICATE_LINE_ITEM for f in run_audit(bill).findings)


# --- math-error -------------------------------------------------------------


def test_math_error_is_a_verified_document_inconsistency():
    bill = clean_bill(total_charges_cents=75000)
    eob = clean_eob()
    result = run_audit(bill, eob)
    (math,) = [f for f in result.findings if f.rule_id == R1_BILL_TOTAL_ARITHMETIC]
    assert (math.status, math.difference_cents) == (FindingStatus.verified_inconsistency, 3000)
    assert "$72,000.00" not in math.explanation and "$720.00" in math.explanation
    assert [e.field for e in math.evidence][:1] == ["total_charges_cents"]
    assert "does not by itself mean" in math.explanation
    assert_sound(result, bill, eob)


def test_unit_price_times_quantity_mismatch_is_flagged():
    bill = clean_bill(total_charges_cents=3000, line_items=[line("li_x", "Lab panel", 3000, code="80053", qty=2, unit=2000)])
    findings = run_audit(bill).findings
    (math,) = [f for f in findings if f.rule_id == R1_BILL_TOTAL_ARITHMETIC]
    assert math.status == FindingStatus.verified_inconsistency
    assert math.difference_cents == 1000
    assert "2 × $20.00" in math.explanation
    assert_sound(run_audit(bill), bill)


def test_price_benchmark_flags_only_material_difference_and_keeps_source_context():
    from app.services.audit import price_benchmark_findings

    bill = clean_bill(line_items=[line("li_x", "Office visit", 52000, code="99214")])
    (finding,) = price_benchmark_findings(bill, {"99214": (10000, "2024")})
    assert finding.category.value == "price_benchmark"
    assert finding.status == FindingStatus.needs_review
    assert finding.difference_cents is None
    assert "Original Medicare Part B" in finding.explanation
    assert "not proof of an error" in finding.explanation
    assert not price_benchmark_findings(bill, {"99214": (40000, "2024")})


def test_math_error_on_partial_extraction_is_only_needs_review():
    bill = clean_bill(total_charges_cents=75000, extraction_quality="partial")
    (math,) = [f for f in run_audit(bill, clean_eob()).findings if f.rule_id == R1_BILL_TOTAL_ARITHMETIC]
    assert math.status == FindingStatus.needs_review
    assert math.missing_information


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"total_charges_cents": None}, "does not show total charges"),
        ({"line_items": []}, "no individual charge lines"),
        ({"line_items": [line("li_1", "Visit", 52000).model_copy(update={"line_total_cents": None})]}, "could not be read"),
        ({"line_items": [line("li_1", "Visit", 92000), line("li_2", "Credit", -20000)]}, "credits or reversals"),
    ],
    ids=["no-total", "no-lines", "unreadable-line", "credits"],
)
def test_unclear_arithmetic_is_not_asserted(overrides, reason):
    result = run_audit(clean_bill(**overrides), clean_eob())
    assert not any(f.rule_id == R1_BILL_TOTAL_ARITHMETIC for f in result.findings)
    assert any(reason in lim for lim in result.limitations)


# --- unmatched-eob / nonfinal-eob / R2 edges --------------------------------


def test_different_claim_ids_with_same_provider_and_date_still_compare_provisionally():
    bill, eob = clean_bill(amount_due_cents=64000), clean_eob(claim_number="OTHER-999")
    result = run_audit(bill, eob)
    (r2,) = [f for f in result.findings if f.rule_id == R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH]
    assert (r2.status, r2.difference_cents) == (FindingStatus.needs_review, 25000)
    assert "identifiers differ" in r2.explanation
    assert any("DEMO-C200" in item and "OTHER-999" in item for item in r2.missing_information)
    assert_sound(result, bill, eob)


def test_conflicting_claim_ids_and_different_provider_compare_as_unverified_uploaded_pair():
    bill = clean_bill(amount_due_cents=64000)
    eob = clean_eob(claim_number="OTHER-999", provider_name="Another Hospital")
    result = run_audit(bill, eob)
    (r2,) = [f for f in result.findings if f.rule_id == R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH]
    assert r2.status == FindingStatus.needs_review
    assert r2.difference_cents == 25000
    assert "claim match not verified" in r2.explanation


def test_uploaded_pair_amounts_are_compared_when_extracted_match_fields_are_missing():
    bill = clean_bill(claim_number=None, provider_name=None, service_date=None, amount_due_cents=64000)
    eob = clean_eob(claim_number=None, provider_name=None, service_date=None, patient_responsibility_cents=39000)
    (r2,) = [
        finding for finding in run_audit(bill, eob).findings
        if finding.rule_id == R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH
    ]
    assert r2.status == FindingStatus.needs_review
    assert r2.difference_cents == 25000
    assert "claim match not verified" in r2.explanation
    assert any("confirm" in item.lower() for item in r2.missing_information)


def test_equal_amounts_are_reported_when_claim_match_is_unverified():
    bill = clean_bill(claim_number=None, provider_name=None, service_date=None, amount_due_cents=39000)
    eob = clean_eob(claim_number=None, provider_name=None, service_date=None, patient_responsibility_cents=39000)
    (r2,) = [
        finding for finding in run_audit(bill, eob).findings
        if finding.rule_id == R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH
    ]
    assert r2.status == FindingStatus.insufficient_information
    assert r2.difference_cents == 0
    assert "amounts match" in r2.title.lower()


def test_missing_amount_reports_missing_balance_instead_of_hiding_it_as_claim_mismatch():
    bill = clean_bill(
        claim_number=None, provider_name=None, service_date=None, amount_due_cents=None
    )
    eob = clean_eob(
        claim_number=None, provider_name=None, service_date=None, patient_responsibility_cents=39000
    )
    (r2,) = [
        finding for finding in run_audit(bill, eob).findings
        if finding.rule_id == R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH
    ]
    assert r2.title == "Bill and EOB amounts could not be compared"
    assert "The current balance or amount due on the bill" in r2.missing_information
    assert "Confirmation that the uploaded bill and EOB refer to the same claim or visit" in r2.missing_information
    assert {ref.field for ref in r2.evidence} == {"patient_responsibility_cents", "claim_number"}


def test_claim_numbers_match_despite_formatting():
    result = run_audit(clean_bill(claim_number="demo c200", amount_due_cents=64000), clean_eob())
    assert rules(result) == [(R2_EOB_PATIENT_RESPONSIBILITY_MISMATCH, FindingStatus.needs_review)]


def test_same_provider_and_date_match_without_claim_numbers():
    bill = clean_bill(claim_number=None, amount_due_cents=64000)
    eob = clean_eob(claim_number=None, provider_name="SAMPLE VALLEY CLINIC, LLC")
    (r2,) = run_audit(bill, eob).findings
    assert r2.status == FindingStatus.needs_review
    assert "same visit" in r2.explanation
    assert any("claim number" in m for m in r2.missing_information)


def test_different_provider_without_claim_numbers_compares_uploaded_pair_with_caveat():
    bill = clean_bill(claim_number=None, amount_due_cents=64000)
    eob = clean_eob(claim_number=None, provider_name="Another Hospital")
    (r2,) = run_audit(bill, eob).findings
    assert r2.status == FindingStatus.needs_review
    assert r2.difference_cents == 25000
    assert "claim match not verified" in r2.explanation


@pytest.mark.parametrize("status", ["Pending", "In Process", "under review"])
def test_nonfinal_eob_is_not_reconciled(status):
    bill, eob = clean_bill(amount_due_cents=64000), clean_eob(eob_status=status)
    result = run_audit(bill, eob)
    (r2,) = result.findings
    assert (r2.status, r2.title) == (FindingStatus.insufficient_information, "EOB is not final yet")
    assert status in r2.explanation
    assert_sound(result, bill, eob)


def test_unknown_eob_status_still_compares_but_says_so():
    (r2,) = run_audit(clean_bill(amount_due_cents=64000), clean_eob(eob_status=None)).findings
    assert r2.status == FindingStatus.needs_review
    assert "A final claim status on the EOB" in r2.missing_information


def test_missing_amounts_cannot_be_compared():
    result = run_audit(clean_bill(amount_due_cents=None), clean_eob())
    (r2,) = result.findings
    assert r2.status == FindingStatus.insufficient_information
    assert r2.missing_information == ["The current balance or amount due on the bill"]


def test_bill_lower_than_eob_suggests_payments_already_applied():
    (r2,) = run_audit(clean_bill(amount_due_cents=29000), clean_eob()).findings
    assert r2.difference_cents == 10000
    assert any("payment you already made" in alt for alt in r2.alternative_explanations)


@pytest.mark.parametrize("difference, severity", [(1, FindingSeverity.low), (4999, FindingSeverity.low), (5000, FindingSeverity.medium)])
def test_severity_scales_with_difference(difference, severity):
    (r2,) = run_audit(clean_bill(amount_due_cents=39000 + difference), clean_eob()).findings
    assert r2.severity == severity


# --- R5 missing information ---------------------------------------------------


def test_failed_eob_extraction_is_reported_and_not_compared():
    eob = clean_eob(extraction_quality="failed", patient_responsibility_cents=None, line_items=[],
                    extraction_warnings=["No billing amounts or line items could be extracted from this document."])
    result = run_audit(clean_bill(amount_due_cents=64000), eob)
    assert rules(result) == [(R5_MISSING_INFORMATION, FindingStatus.insufficient_information)]
    assert result.findings[0].title == "The EOB could not be read"
    assert_sound(result, clean_bill(), eob)


def test_partial_extraction_adds_a_limitation():
    result = run_audit(clean_bill(extraction_quality="partial"), clean_eob())
    assert any("could not be read reliably" in lim for lim in result.limitations)


def test_estimate_below_bill_amount_does_not_trigger_gfe_finding():
    result = run_audit(clean_bill(), clean_eob(), estimate_doc())
    assert result.findings == []
    assert not any("comparison is not supported" in lim for lim in result.limitations)


@pytest.mark.parametrize("difference", [40000, 50000])
def test_gfe_difference_at_or_above_400_dollars_is_flagged(difference):
    bill = clean_bill(amount_due_cents=50000 + difference)
    estimate = estimate_doc(expected_total_cents=50000)
    result = run_audit(bill, None, estimate)
    (finding,) = [f for f in result.findings if f.rule_id == R6_GFE_PATIENT_AMOUNT_THRESHOLD]
    assert finding.status == FindingStatus.needs_review
    assert finding.difference_cents == difference
    assert "Sana's $400 patient-balance review trigger" in finding.explanation
    assert "does not determine eligibility" in finding.explanation
    assert [ref.document_id for ref in finding.evidence] == [bill.id, estimate.id]
    assert_sound(result, bill, estimate)


def test_gfe_difference_just_below_400_dollars_is_not_threshold_alert():
    result = run_audit(
        clean_bill(amount_due_cents=89999), None, estimate_doc(expected_total_cents=50000)
    )
    (finding,) = [f for f in result.findings if f.rule_id == R6_GFE_PATIENT_AMOUNT_THRESHOLD]
    assert finding.severity == FindingSeverity.info
    assert "below Sana's $400 patient-balance review trigger" in finding.explanation


def test_gfe_documents_with_different_providers_are_not_compared():
    result = run_audit(
        clean_bill(amount_due_cents=100000), None,
        estimate_doc(expected_total_cents=50000, provider_name="Different Medical Center"),
    )
    (finding,) = [f for f in result.findings if f.rule_id == R6_GFE_PATIENT_AMOUNT_THRESHOLD]
    assert finding.status == FindingStatus.insufficient_information


def test_documents_must_be_passed_in_the_right_slots():
    with pytest.raises(ValueError):
        run_audit(clean_eob())


@pytest.mark.parametrize(
    "cents, text", [(0, "$0.00"), (5, "$0.05"), (64000, "$640.00"), (123456789, "$1,234,567.89"), (-2500, "-$25.00")]
)
def test_format_usd(cents, text):
    assert format_usd(cents) == text
