"""Synthetic protocol/proof checks, not measurements of a language model.

The transport below never opens a socket.  It supplies adversarial Ollama
responses to the real verifier so tests exercise aggregation and grounding.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re

import pytest

from research.core_mvp import assessment
from research.core_mvp.llm_assessment import LlmAssessmentVerifier


DIGEST = "sha256:" + "a" * 64
MODEL = {
    "backend": "ollama", "model": "qwen3.5:4b", "digest": DIGEST,
    "endpoint": "http://127.0.0.1:11434",
}
POLICY = {"enabled": True}
POSITIVE = "All client traffic travels through a secured channel before reaching the service."
NEGATIVE = "All client traffic is transmitted in clear text in the deployed service."


class FakeOllama:
    def __init__(self, content=None, *, done=True, done_reason="stop", error=None,
                 digest=DIGEST, digests=None, models=None, telemetry=None,
                 model_name="qwen3.5:4b"):
        self.content = content
        self.done = done
        self.done_reason = done_reason
        self.error = error
        self.digest = digest
        self.digests = digests
        self.models = models
        self.telemetry = telemetry or {}
        self.model_name = model_name
        self.calls = []
        self.tag_calls = 0

    def request(self, method, path, payload=None, *, timeout, max_bytes):
        self.calls.append((method, path, deepcopy(payload), timeout, max_bytes))
        if path == "/api/tags":
            if self.models is not None:
                return {"models": deepcopy(self.models)}
            digest = self.digest
            if self.digests:
                digest = self.digests[min(self.tag_calls, len(self.digests) - 1)]
            self.tag_calls += 1
            return {"models": [{"name": self.model_name, "digest": digest}]}
        if path == "/api/show":
            return {"template": "synthetic chat template", "details": {
                "format": "gguf", "family": "qwen3_5", "parameter_size": "4B",
                "quantization_level": "Q4_K_M",
            }, "model_info": {}}
        assert path == "/api/chat", f"Unexpected endpoint {path}"
        if self.error is not None:
            raise self.error
        raw_content = self.content(payload) if callable(self.content) else self.content
        content = raw_content if isinstance(raw_content, str) else json.dumps(raw_content)
        return {
            "model": self.model_name, "done": self.done, "done_reason": self.done_reason,
            "message": {"role": "assistant", "content": content},
            "prompt_eval_count": 200, "eval_count": 70,
            **self.telemetry,
        }

    @property
    def chat_calls(self):
        return [call for call in self.calls if call[1] == "/api/chat"]


def checklist(*requirement_ids):
    return {
        "checklist_id": "C1.1", "criterion_id": "C1", "mode": "LOCAL",
        "importance": "REQUIRED", "query": "client traffic service security",
        "statement": "The deployed service encrypts client requests in transit.",
        "requirements": [{
            "requirement_id": requirement_id,
            "description": "Client requests are encrypted in transit.",
            "any_of": ["request encryption"],
        } for requirement_id in (requirement_ids or ("encryption",))],
        "contradiction_patterns": [],
    }


def scoped_pack(*texts):
    chunks = []
    candidates = []
    for index, text in enumerate(texts or (POSITIVE,)):
        chunk_id = f"report-chunk-{index + 1}"
        chunks.append({
            "chunk_id": chunk_id, "document_id": "synthetic-report",
            "document_version_id": "synthetic-report-v1", "text": text,
            "normalized_text": text, "source_spans": [{
                "document_id": "synthetic-report",
                "document_version_id": "synthetic-report-v1",
                "element_key": f"P{index + 1:04d}",
                "chunk_normalized_char_start": 0,
                "chunk_normalized_char_end": len(text),
            }],
        })
        candidates.append({
            "chunk_id": chunk_id, "document_id": "synthetic-report",
            "rank": index + 1, "score": 1.0,
        })
    mapping, report_id, report_version = assessment._report_scope(chunks)
    return assessment._validated_evidence_pack(
        candidates, mapping, report_id=report_id, report_version=report_version,
    )


def requirement(relation="SUPPORTED", *, requirement_id="encryption",
                quote=POSITIVE, evidence_id="evidence-report-chunk-1"):
    return {
        "requirement_id": requirement_id, "relation": relation,
        "rationale": "Synthetic assessment supplied by the fake transport.",
        "evidence": [] if relation == "INSUFFICIENT" else [{
            "evidence_id": evidence_id, "quote": quote,
        }],
    }


def response(*requirements):
    return {"checklist_id": "C1.1", "requirements": list(requirements or (requirement(),))}


def verify(content=None, *, pack=None, item=None, policy=None, **transport_options):
    transport = FakeOllama(response() if content is None else content, **transport_options)
    verifier = LlmAssessmentVerifier(MODEL, policy or POLICY, transport=transport)
    result = verifier.verify(item or checklist(), scoped_pack() if pack is None else pack)
    return result, transport, verifier


def assert_unknown(result):
    assert result["verification_relation"] == "INSUFFICIENT"
    assert result["checklist_outcome"] == "CANNOT_ASSESS"
    assert result["reason_code"]
    assert result["rationale"]


def test_semantic_support_maps_an_exact_quote_without_literal_requirement_match():
    result, transport, _ = verify()
    assert "request encryption" not in POSITIVE.casefold()
    assert result["checklist_outcome"] == "MET"
    assert result["verification_relation"] == "SUPPORTED"
    [proof] = result["matched_evidence_spans"]
    assert proof["evidence_id"] == "evidence-report-chunk-1"
    assert proof["span"]["text"] == POSITIVE
    assert proof["span"]["normalized_start"] == 0
    assert proof["span"]["normalized_end"] == len(POSITIVE)
    assert transport.chat_calls


def test_direct_counterevidence_has_grounded_contradiction_proof():
    result, _, _ = verify(
        response(requirement("CONTRADICTED", quote=NEGATIVE)),
        pack=scoped_pack(NEGATIVE),
    )
    assert result["checklist_outcome"] == "UNMET"
    assert result["verification_relation"] == "CONTRADICTED"
    [proof] = result["contradiction_hits"]
    assert proof["span"]["text"] == NEGATIVE


def test_every_requirement_needs_support_to_reach_met():
    item = checklist("encryption", "deployment")
    result, _, _ = verify(response(
        requirement(), requirement("INSUFFICIENT", requirement_id="deployment"),
    ), item=item)
    assert_unknown(result)
    assert result["requirements_satisfied"] == 1
    assert result["requirements_total"] == 2


def test_counterevidence_for_one_required_condition_can_fail_the_conjunction():
    item = checklist("encryption", "deployment")
    result, _, _ = verify(response(
        requirement(), requirement("CONTRADICTED", requirement_id="deployment",
                                   quote=NEGATIVE, evidence_id="evidence-report-chunk-2"),
    ), item=item, pack=scoped_pack(POSITIVE, NEGATIVE))
    assert result["checklist_outcome"] == "UNMET"


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(checklist_id="another-checklist"),
    lambda value: value.update(requirements=[]),
    lambda value: value["requirements"].append(deepcopy(value["requirements"][0])),
    lambda value: value["requirements"][0].update(requirement_id="unknown-requirement"),
    lambda value: value["requirements"][0].update(relation="MET"),
    lambda value: value["requirements"][0].update(relation="UNSURE"),
    lambda value: value.update(score=10),
    lambda value: value.update(checklist_outcome="MET"),
    lambda value: value["requirements"][0].update(score=10),
    lambda value: value["requirements"][0].update(evidence=[]),
    lambda value: value["requirements"][0].update(rationale=""),
    lambda value: value["requirements"][0]["evidence"][0].update(evidence_id="foreign-evidence"),
    lambda value: value["requirements"][0]["evidence"][0].update(quote="Fabricated quotation."),
    lambda value: value["requirements"][0]["evidence"][0].update(quote=""),
    lambda value: value["requirements"][0]["evidence"][0].update(quote="   "),
    lambda value: value["requirements"][0]["evidence"][0].update(start=0, end=10),
    lambda value: value["requirements"][0]["evidence"][0].update(document_version_id="foreign-v2"),
])
def test_bad_structures_and_unbound_evidence_never_become_conclusive(mutate):
    content = response()
    mutate(content)
    result, _, _ = verify(content)
    assert_unknown(result)


def test_one_missing_requirement_is_not_assumed_satisfied():
    result, _, _ = verify(item=checklist("encryption", "deployment"))
    assert_unknown(result)


def test_duplicate_requirement_with_conflicting_relations_cannot_choose_a_winner():
    result, _, _ = verify(response(
        requirement(), requirement("CONTRADICTED", quote=NEGATIVE),
    ), pack=scoped_pack(POSITIVE + " " + NEGATIVE))
    assert_unknown(result)


def test_quote_repeated_in_one_chunk_requires_unambiguous_evidence():
    result, _, _ = verify(pack=scoped_pack(POSITIVE + " " + POSITIVE))
    assert_unknown(result)


def test_quote_in_a_different_pack_chunk_cannot_be_bound_to_the_wrong_id():
    result, _, _ = verify(pack=scoped_pack(NEGATIVE, POSITIVE))
    assert_unknown(result)


def test_text_outside_the_supplied_pack_cannot_be_quoted():
    result, _, _ = verify(pack=scoped_pack(NEGATIVE))
    assert_unknown(result)


@pytest.mark.parametrize("field", ["document_id", "document_version_id"])
def test_duck_typed_entry_cannot_detach_record_from_its_canonical_scope(field):
    pack = deepcopy(scoped_pack())
    pack[0].record[field] = "foreign-scope"
    result, _, _ = verify(pack=pack)
    assert_unknown(result)


@pytest.mark.parametrize("content", [
    "this is not JSON",
    "```json\n{}\n```",
    '{"checklist_id":"C1.1", "checklist_id":"other", "requirements":[]}',
    '{"checklist_id":"C1.1", "requirements": [',
    "[]", "null",
])
def test_invalid_json_never_falls_back_to_a_phrase_positive(content):
    pack = scoped_pack("The report describes request encryption as completed work.")
    result, _, _ = verify(content, pack=pack)
    assert_unknown(result)


@pytest.mark.parametrize(("done", "done_reason"), [(False, "stop"), (True, "length")])
def test_incomplete_generation_is_unknown_even_if_the_content_looks_valid(done, done_reason):
    result, _, _ = verify(done=done, done_reason=done_reason)
    assert_unknown(result)


@pytest.mark.parametrize("error", [TimeoutError("synthetic timeout"), OSError("offline")])
def test_transport_failure_is_unknown_and_does_not_run_a_second_verifier(error):
    result, _, _ = verify(error=error)
    assert_unknown(result)


def test_missing_local_model_does_not_pull_or_generate():
    result, transport, _ = verify(models=[])
    assert_unknown(result)
    assert transport.chat_calls == []
    assert not any("pull" in call[1] for call in transport.calls)


def test_wrong_digest_cannot_silently_run_another_checkpoint():
    result, transport, _ = verify(digest="sha256:" + "b" * 64)
    assert_unknown(result)
    assert transport.chat_calls == []


def test_ollama_plain_hex_digest_matches_the_explicitly_prefixed_pin():
    result, _, verifier = verify(digest="a" * 64)
    assert result["checklist_outcome"] == "MET"
    assert verifier.metadata["digest"] == DIGEST


def test_plain_hex_configuration_is_canonicalized_to_a_prefixed_digest():
    verifier = LlmAssessmentVerifier(
        {**MODEL, "digest": "a" * 64}, POLICY, transport=FakeOllama(response()),
    )
    assert verifier.metadata["digest"] == DIGEST
    assert verifier.verify(checklist(), scoped_pack())["checklist_outcome"] == "MET"


def test_model_tag_change_during_generation_invalidates_the_result():
    result, _, _ = verify(digests=[DIGEST, DIGEST, "sha256:" + "b" * 64])
    assert_unknown(result)


def test_empty_evidence_pack_is_unknown_without_a_generation_request():
    result, transport, _ = verify(pack=[])
    assert_unknown(result)
    assert transport.chat_calls == []


def test_huge_evidence_is_not_silently_truncated_and_used_for_a_verdict():
    result, transport, _ = verify(pack=scoped_pack("A" * 1_000_000))
    assert_unknown(result)
    assert transport.chat_calls == []


def test_serialized_prompt_budget_is_checked_even_when_raw_evidence_fits_its_own_limit():
    result, transport, _ = verify(policy={"enabled": True, "num_ctx": 2048, "num_predict": 128})
    assert_unknown(result)
    assert transport.chat_calls == []
    assert result["reason_code"] == "LLM_INPUT_BUDGET_EXCEEDED"


@pytest.mark.parametrize("telemetry", [
    {"prompt_eval_count": 16384},
    {"eval_count": 1537},
    {"eval_count": -1},
    {"prompt_eval_count": True},
    {"total_duration": "200"},
])
def test_observed_context_or_generation_overflow_is_not_accepted(telemetry):
    result, transport, _ = verify(telemetry=telemetry)
    assert transport.chat_calls
    assert_unknown(result)


def test_one_verifier_instance_has_a_bounded_number_of_generation_calls():
    transport = FakeOllama(response())
    verifier = LlmAssessmentVerifier(MODEL, {"enabled": True, "max_checklists": 1}, transport=transport)
    assert verifier.verify(checklist(), scoped_pack())["checklist_outcome"] == "MET"
    result = verifier.verify(checklist(), scoped_pack())
    assert_unknown(result)
    assert result["reason_code"] == "LLM_CHECKLIST_BUDGET_EXCEEDED"
    assert len(transport.chat_calls) == 1


def test_unavailable_ollama_during_startup_yields_a_safe_unknown():
    class Offline(FakeOllama):
        def request(self, *_args, **_kwargs):
            raise OSError("synthetic connection unavailable")

    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=Offline())
    assert_unknown(verifier.verify(checklist(), scoped_pack()))


def test_real_transport_disables_environment_proxies_and_rejects_redirects(monkeypatch):
    from research.core_mvp import llm_assessment

    captured = []
    monkeypatch.setenv("HTTP_PROXY", "http://unreachable.example:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://unreachable.example:8080")
    monkeypatch.setattr(llm_assessment.request, "build_opener", lambda *handlers: captured.extend(handlers))
    llm_assessment.OllamaJsonTransport()
    [proxy] = [handler for handler in captured if isinstance(handler, llm_assessment.request.ProxyHandler)]
    assert proxy.proxies == {}
    [redirect] = [handler for handler in captured if isinstance(handler, llm_assessment.request.HTTPRedirectHandler)]
    with pytest.raises(Exception, match="REDIRECT_REJECTED"):
        redirect.redirect_request(None, None, 302, "redirect", {}, "http://outside.example")


@pytest.mark.parametrize(("body", "max_bytes"), [
    (b'{"ready": true}' * 1000, 1024),
    (b'{"ready": true, "ready": false}', 1024),
    (b'not JSON', 1024),
    (b'[]', 1024),
])
def test_real_transport_bounds_and_parses_the_actual_response_bytes(monkeypatch, body, max_bytes):
    from research.core_mvp import llm_assessment

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, count):
            assert count == max_bytes + 1
            return body[:count]

    class Opener:
        def open(self, req, *, timeout):
            assert req.full_url == "http://127.0.0.1:11434/api/tags"
            assert timeout == 3
            return Response()

    monkeypatch.setattr(llm_assessment.request, "build_opener", lambda *_handlers: Opener())
    transport = llm_assessment.OllamaJsonTransport()
    with pytest.raises(Exception, match="LLM_RESPONSE_TOO_LARGE|LLM_INVALID_RESPONSE"):
        transport.request("GET", "/api/tags", timeout=3, max_bytes=max_bytes)


def test_metadata_pins_the_actual_model_and_prompt_contract():
    _, transport, verifier = verify()
    metadata = verifier.metadata
    serialized = json.dumps(metadata)
    assert DIGEST in serialized or "a" * 64 in serialized
    hashes = [value for key, value in metadata.items() if "sha256" in key]
    assert len(hashes) >= 2
    assert all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)
    [request] = transport.chat_calls
    payload = request[2]
    assert payload["stream"] is False
    assert isinstance(payload["format"], dict)
    assert request[3] > 0 and request[4] > 0


@pytest.mark.parametrize("patch", [
    {"endpoint": "https://example.com"},
    {"endpoint": "http://127.0.0.1:11434/path"},
    {"digest": "latest"},
    {"backend": "unknown"},
])
def test_invalid_model_configuration_is_not_silently_accepted(patch):
    config = {**MODEL, **patch}
    with pytest.raises(ValueError):
        LlmAssessmentVerifier(config, POLICY, transport=FakeOllama(response()))


CONFIG = {
    "candidate_depth": 3, "rerank_depth": 3, "top_k": 3,
    "dense_enabled": False, "reranker_enabled": False,
}


def rubric():
    return {
        "schema_version": 1, "rubric_id": "synthetic-semantic-contract",
        "version": "1", "max_score": 10,
        "criteria": [{
            "criterion_id": "C1", "title": "In-transit encryption", "weight": 10,
            "checklists": [checklist()],
        }],
    }


def parsed_chunks(tmp_path, text=POSITIVE):
    from research.core_mvp.documents import parse_document

    path = tmp_path / "report.txt"
    path.write_text(text, encoding="utf-8")
    return parse_document(path, role="student-report", min_tokens=1).chunks


def assert_report_contracts(report):
    from research.core_mvp.contracts import validate_assessment_report
    from research.schema_validation import validate_json_schema

    validate_assessment_report(report)
    validate_json_schema(report, kind="assessment")


def test_opt_in_semantic_pipeline_keeps_real_parser_proof_and_deterministic_score(tmp_path, monkeypatch):
    chunks = parsed_chunks(tmp_path)
    content = response(requirement(evidence_id=f"evidence-{chunks[0]['chunk_id']}"))
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=FakeOllama(content))

    def no_phrase_fallback(*_args, **_kwargs):
        pytest.fail("The enabled semantic path called the phrase verifier")

    monkeypatch.setattr(assessment, "_verify", no_phrase_fallback)
    report = assessment.run_assessment_pipeline(
        chunks, rubric(), config={**CONFIG, "llm_verification": POLICY},
        encoder=None, reranker=None, llm_verifier=verifier,
    )
    assert report["verification_method"] == "LOCAL_LLM_REQUIREMENT_VERIFIER_V1"
    assert report["checklist_results"][0]["checklist_outcome"] == "MET"
    assert report["proposed_total_score"] == 10.0
    assert_report_contracts(report)


def test_disabled_policy_preserves_the_entire_old_output_and_never_calls_injected_verifier(tmp_path):
    chunks = parsed_chunks(tmp_path, "The service completed request encryption.")
    baseline = assessment.run_assessment_pipeline(
        chunks, rubric(), config=CONFIG, encoder=None, reranker=None,
    )

    class MustNotUse:
        def verify(self, *_args, **_kwargs):
            pytest.fail("Disabled policy called the semantic verifier")

    ignored = assessment.run_assessment_pipeline(
        chunks, rubric(), config=CONFIG, encoder=None, reranker=None,
        llm_verifier=MustNotUse(),
    )
    assert ignored == baseline
    assert baseline["verification_method"] == "SCOPED_PHRASE_CONTEXT_V4"
    assert baseline["proposed_total_score"] == 10.0
    assert_report_contracts(ignored)


def test_enabled_policy_requires_explicitly_loaded_verifier_at_the_core_boundary(tmp_path):
    with pytest.raises(ValueError):
        assessment.run_assessment_pipeline(
            parsed_chunks(tmp_path), rubric(),
            config={**CONFIG, "llm_verification": POLICY},
            encoder=None, reranker=None,
        )


def test_malformed_semantic_response_withholds_score_even_when_old_phrase_path_would_pass(tmp_path):
    chunks = parsed_chunks(tmp_path, "The service completed request encryption.")
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=FakeOllama("not JSON"))
    report = assessment.run_assessment_pipeline(
        chunks, rubric(), config={**CONFIG, "llm_verification": POLICY},
        encoder=None, reranker=None, llm_verifier=verifier,
    )
    [item] = report["checklist_results"]
    assert_unknown(item)
    assert report["criterion_results"][0]["proposed_score"] is None
    assert report["proposed_total_score"] is None
    assert report["requires_lecturer_review"] is True
    assert_report_contracts(report)


@pytest.mark.parametrize("pipeline", ["similarity", "assessment", "both"])
def test_runner_loads_semantic_assessment_only_for_selected_assessment_pipeline(tmp_path, monkeypatch, pipeline):
    from pathlib import Path
    from research.core_mvp import llm_assessment, runner

    fixture = Path(__file__).parent / "fixtures" / "core_mvp"
    raw_config = json.loads((fixture / "config-bm25-only.json").read_text(encoding="utf-8"))
    raw_config["pipeline2"]["llm_verification"] = POLICY
    raw_config.setdefault("models", {})["assessment_verifier"] = MODEL
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(raw_config), encoding="utf-8")
    loads = []

    def fake_loader(model_config, policy):
        loads.append((deepcopy(model_config), deepcopy(policy)))
        return LlmAssessmentVerifier(model_config, policy, transport=FakeOllama(models=[]))

    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", fake_loader)
    result = runner.run_core_mvp(
        report_path=fixture / "report.txt",
        source_paths=[fixture / "source-overlap.txt"],
        rubric_path=fixture / "rubric.json", config_path=config_file,
        output_dir=tmp_path / "run", pipeline=pipeline,
    )
    assert len(loads) == (0 if pipeline == "similarity" else 1)
    if pipeline != "similarity":
        report = json.loads(Path(result["output_paths"]["assessment_report"]).read_text(encoding="utf-8"))
        assert report["proposed_total_score"] is None
        assert_report_contracts(report)


def semantic_report(tmp_path, relation="SUPPORTED"):
    text = NEGATIVE if relation == "CONTRADICTED" else POSITIVE
    chunks = parsed_chunks(tmp_path, text)
    content = response(requirement(
        relation, quote=text, evidence_id=f"evidence-{chunks[0]['chunk_id']}",
    ))
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=FakeOllama(content))
    report = assessment.run_assessment_pipeline(
        chunks, rubric(), config={**CONFIG, "llm_verification": POLICY},
        encoder=None, reranker=None, llm_verifier=verifier,
    )
    assert_report_contracts(report)
    return report


@pytest.mark.parametrize("field", [
    "backend", "model", "digest", "prompt_sha256", "output_schema_sha256", "policy_sha256",
])
def test_persisted_semantic_report_cannot_drop_model_or_prompt_provenance(tmp_path, field):
    from research.core_mvp.contracts import validate_assessment_report
    from research.schema_validation import validate_json_schema

    report = semantic_report(tmp_path)
    del report["verification_metadata"][field]
    with pytest.raises(ValueError):
        validate_assessment_report(report)
    with pytest.raises(ValueError):
        validate_json_schema(report, kind="assessment")


@pytest.mark.parametrize("mutate", [
    lambda item: item.update(requirement_results=[]),
    lambda item: item["requirement_results"].append(deepcopy(item["requirement_results"][0])),
    lambda item: item["requirement_results"][0].update(requirement_id="unknown-requirement"),
    lambda item: item["requirement_results"][0].update(satisfied=False),
    lambda item: item.update(requirements_total=2),
    lambda item: item.update(requirements_satisfied=0),
    lambda item: item.update(verification_relation="INSUFFICIENT", checklist_outcome="CANNOT_ASSESS"),
    lambda item: item["matched_evidence_spans"][0].update(requirement_id="unknown-requirement"),
])
def test_persisted_semantic_decisions_cannot_discard_or_reinterpret_authored_requirements(tmp_path, mutate):
    from research.core_mvp.contracts import validate_assessment_report

    report = semantic_report(tmp_path)
    mutate(report["checklist_results"][0])
    with pytest.raises(ValueError):
        validate_assessment_report(report)


def test_persisted_counterevidence_must_be_linked_to_a_contradicted_requirement(tmp_path):
    from research.core_mvp.contracts import validate_assessment_report

    report = semantic_report(tmp_path, "CONTRADICTED")
    report["checklist_results"][0]["contradiction_hits"][0]["requirement_id"] = "unknown-requirement"
    with pytest.raises(ValueError, match="linked contradiction proof|detached"):
        validate_assessment_report(report)


@pytest.mark.parametrize("mutate", [
    lambda report: report.update(proposed_total_score=9),
    lambda report: report.update(assessable_subtotal=9),
    lambda report: report["criterion_results"][0].update(proposed_score=9),
    lambda report: report.update(max_score=100),
])
def test_persisted_semantic_report_cannot_change_python_owned_scores(tmp_path, mutate):
    from research.core_mvp.contracts import validate_assessment_report

    report = semantic_report(tmp_path)
    mutate(report)
    with pytest.raises(ValueError):
        validate_assessment_report(report)


def test_persisted_unknown_cannot_hide_the_required_review_flag(tmp_path):
    from research.core_mvp.contracts import validate_assessment_report

    report = semantic_report(tmp_path, "INSUFFICIENT")
    report["requires_lecturer_review"] = False
    with pytest.raises(ValueError):
        validate_assessment_report(report)


@pytest.mark.parametrize("valid_response", [True, False])
def test_backend_snapshot_uses_the_real_pipeline_and_output_contracts(tmp_path, monkeypatch, valid_response):
    from pathlib import Path
    from research.core_mvp import llm_assessment
    from research.core_mvp.rubric import compile_rubric
    from services.backend.src.kltn_ai.worker import bounded_pipeline

    root = Path(__file__).resolve().parents[2]
    profile_id = "bm25-p2-llm-v1"
    profile = json.loads((root / "services/backend/configs" / f"{profile_id}.json").read_text())
    profile["models"]["assessment_verifier"]["digest"] = DIGEST
    profile_path = tmp_path / "services/backend/configs" / f"{profile_id}.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    monkeypatch.setattr(bounded_pipeline, "ROOT", tmp_path)
    _, config_hash = bounded_pipeline.configuration(profile_id)
    chunks = parsed_chunks(tmp_path)
    content = response(requirement(evidence_id=f"evidence-{chunks[0]['chunk_id']}")) if valid_response else "not JSON"
    transport = FakeOllama(content, model_name=profile["models"]["assessment_verifier"]["model"])
    loaded = []

    def fake_loader(model_config, policy):
        loaded.append(deepcopy(model_config))
        return LlmAssessmentVerifier(model_config, policy, transport=transport)

    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", fake_loader)
    result = bounded_pipeline.execute_snapshot({
        "config_id": profile_id, "config_sha256": config_hash, "run_type": "ASSESSMENT",
        "report_chunks": list(chunks), "source_chunks": [], "compiled_rubric": compile_rubric(rubric()),
    })
    assert len(loaded) == 1
    assert result["similarity"] is None
    report = result["assessment"]
    assert report["checklist_results"][0]["checklist_outcome"] == ("MET" if valid_response else "CANNOT_ASSESS")
    assert report["proposed_total_score"] == (10.0 if valid_response else None)
    assert result["execution"]["models"]["assessment_verifier"]["digest"] == DIGEST
    assert result["execution"]["hardware"]["device"] == "local_model_service"
    assert_report_contracts(report)
