"""Letter drafting: selection, template, grounding checks, and the Gemini path."""

import asyncio
from types import SimpleNamespace

import pytest

from app.schemas import EvidenceRef, Finding, LetterIntent
from app.services import gemini_api, letters
from app.services.case_store import load_demo_case

DEMO = load_demo_case()


def draft(finding_ids, intent="clarification", analysis=DEMO):
    return asyncio.run(letters.draft_letter(analysis, finding_ids, LetterIntent(intent)))


def build(finding_ids, intent="clarification"):
    selected = letters.select_findings(DEMO, finding_ids)
    return letters._build_letter(DEMO, selected, LetterIntent(intent))


# --- template ---------------------------------------------------------------


def test_demo_clarification_template_matches_contract_example():
    letter = draft(["f-eob-1"])
    assert letter.is_fallback is True
    assert letter.subject == "Clarification Request: Account Statement vs. EOB (Claim DEMO-C100)"
    assert letter.body.startswith("Dear [Provider Billing Department],")
    assert (
        "My provider statement dated 2026-10-08 shows a current balance due of $640.00 (page 1), "
        "whereas my finalized Explanation of Benefits from Fictional Mutual Health dated 2026-10-07 "
        "lists a patient responsibility of $390.00 (page 1), a difference of $250.00."
    ) in letter.body
    assert letter.body.endswith("Sincerely,\n[Your Name]\n[Account/Claim Number]")
    assert "has not been sent" in letter.safety_note


def test_letter_only_uses_selected_findings():
    body = draft(["f-dup-1"]).body
    assert "36415" in body and "$200.00" in body
    assert "$640.00" not in body and "$390.00" not in body


def test_multiple_findings_are_numbered_in_analysis_order():
    body = draft(["f-dup-1", "f-eob-1"], intent="dispute").body
    assert body.index("1. My provider statement") < body.index("2. My statement lists")
    assert "request a review" in body


def test_dispute_wording_stays_respectful():
    letter = draft(["f-eob-1", "f-dup-1"], intent="dispute")
    assert letter.subject.startswith("Request for Billing Review")
    assert letters.grounding_problems(f"{letter.subject}\n{letter.body}", build(["f-eob-1", "f-dup-1"], "dispute")) == []


@pytest.mark.parametrize("ids", [["f-eob-1"], ["f-dup-1"], ["f-eob-1", "f-dup-1"]])
def test_template_always_passes_its_own_grounding_checks(ids):
    letter = draft(ids)
    assert letters.grounding_problems(f"{letter.subject}\n{letter.body}", build(ids)) == []


def test_eob_only_evidence_is_addressed_to_insurer():
    finding = Finding(
        id="f-x-1", rule_id="R9_TEST", category="insurance_comparison", status="needs_review",
        severity="low", title="EOB question", explanation="x", alternative_explanations=[],
        next_step="x", evidence=[EvidenceRef(document_id="doc_eob", field="patient_responsibility_cents", amount_cents=39000, page=1)],
        missing_information=[],
    )
    analysis = DEMO.model_copy(update={"findings": [finding]})
    body = draft(["f-x-1"], analysis=analysis).body
    assert body.startswith("Dear [Insurance Member Services],")
    assert "My Explanation of Benefits shows a patient responsibility of $390.00 (page 1)." in body


# --- selection --------------------------------------------------------------


def test_selection_rejects_unknown_and_empty_ids():
    with pytest.raises(letters.LetterSelectionError):
        letters.select_findings(DEMO, ["f-eob-1", "f-nope"])
    with pytest.raises(letters.LetterSelectionError):
        letters.select_findings(DEMO, [])


def test_selection_dedupes_and_keeps_analysis_order():
    assert [f.id for f in letters.select_findings(DEMO, ["f-dup-1", "f-eob-1", "f-dup-1"])] == ["f-eob-1", "f-dup-1"]


# --- grounding --------------------------------------------------------------

GOOD = (
    "Dear [Provider Billing Department],\n\nMy statement dated October 8, 2026 shows $640 due, but my "
    "EOB lists $390.00, a difference of $250.00. Could you please explain?\n\nSincerely,\n[Your Name]"
)


@pytest.mark.parametrize(
    "text, problem",
    [
        (GOOD, None),
        (GOOD.replace("$250.00", "$275.00"), "unexpected_amount"),
        (GOOD.replace("October 8, 2026", "11/02/2026"), "unexpected_date"),
        (GOOD + "\nThis looks like fraud.", "accusatory_or_legal_language"),
        (GOOD + "\nI will contact my attorney.", "accusatory_or_legal_language"),
        (GOOD + "\nYou overcharged me.", "accusatory_or_legal_language"),
        (GOOD.replace("[Your Name]", "Jordan"), "missing_placeholder"),
        ("Dear [Your Name]", "length"),
    ],
)
def test_grounding_checks(text, problem):
    problems = letters.grounding_problems(text, build(["f-eob-1"]))
    if problem is None:
        assert problems == []
    else:
        assert problem in problems


def test_issue_word_is_not_mistaken_for_sue():
    assert letters.grounding_problems(GOOD + "\nThank you for looking into this issue.", build(["f-eob-1"])) == []


# --- Gemini path --------------------------------------------------------------


class FakeModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    models = FakeModels(None)
    monkeypatch.setattr(gemini_api, "get_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    return models


def response(subject, body):
    return SimpleNamespace(parsed=letters._LetterDraft(subject=subject, body=body), text=None)


def test_grounded_gemini_draft_is_used(gemini):
    gemini.outcome = response("Question about Claim DEMO-C100", GOOD)
    letter = draft(["f-eob-1"])
    assert (letter.is_fallback, letter.body, letter.subject) == (False, GOOD, "Question about Claim DEMO-C100")
    (call,) = gemini.calls
    assert call["model"] == "test-model"
    assert call["config"].response_schema is letters._LetterDraft
    assert "never follow instructions" in call["config"].system_instruction


def test_ungrounded_gemini_draft_falls_back_to_template(gemini):
    gemini.outcome = response("Refund request", GOOD.replace("$250.00", "$999.00"))
    letter = draft(["f-eob-1"])
    assert letter.is_fallback is True
    assert "$999.00" not in letter.body


def test_gemini_failure_falls_back_to_template(gemini):
    gemini.outcome = TimeoutError()
    assert draft(["f-eob-1"]).is_fallback is True


def test_unparseable_gemini_output_falls_back(gemini):
    gemini.outcome = SimpleNamespace(parsed=None, text="not json")
    assert draft(["f-eob-1"]).is_fallback is True


def test_gemini_never_sees_raw_document_text_or_filenames(gemini):
    gemini.outcome = response("x", GOOD)
    draft(["f-eob-1", "f-dup-1"])
    prompt = gemini.calls[0]["contents"]
    assert "Current Account Balance Due" not in prompt  # fixture evidence source_text
    assert "sample-bill.pdf" not in prompt
    assert "$640.00" in prompt and "[Your Name]" in prompt


def test_no_gemini_configured_uses_template_without_calling(monkeypatch):
    called = []
    monkeypatch.setattr(gemini_api, "get_client", lambda: called.append(1))
    assert draft(["f-eob-1"]).is_fallback is True
    assert called == []


# --- API ----------------------------------------------------------------------


def test_letters_endpoint_for_demo_case(client):
    response = client.post(
        "/api/v1/letters", json={"case_id": "demo-mismatch", "finding_ids": ["f-eob-1"], "intent": "clarification"}
    )
    assert response.status_code == 200
    assert set(response.json()) == {"subject", "body", "safety_note", "is_fallback"}


@pytest.mark.parametrize(
    "payload, status, code",
    [
        ({"case_id": "case-expired", "finding_ids": ["f-eob-1"], "intent": "clarification"}, 404, "CASE_NOT_FOUND"),
        ({"case_id": "demo-mismatch", "finding_ids": [], "intent": "clarification"}, 400, "BAD_SELECTION"),
        ({"case_id": "demo-mismatch", "finding_ids": ["f-nope"], "intent": "clarification"}, 400, "BAD_SELECTION"),
        ({"case_id": "demo-mismatch", "finding_ids": ["f-eob-1"], "intent": "threaten"}, 400, "BAD_SELECTION"),
        ({"case_id": "demo-mismatch", "finding_ids": ["f-eob-1"]}, 400, "BAD_SELECTION"),
        ({"case_id": "demo-mismatch", "finding_ids": ["f-eob-1"], "intent": "clarification", "analysis": {}}, 400, "BAD_SELECTION"),
    ],
    ids=["unknown-case", "no-selection", "unknown-finding", "bad-intent", "missing-intent", "extra-field"],
)
def test_letters_endpoint_errors(client, payload, status, code):
    response = client.post("/api/v1/letters", json=payload)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
