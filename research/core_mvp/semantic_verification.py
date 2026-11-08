"""Opt-in, segment-level semantic equivalence from bidirectional NLI.

NLI probabilities are model outputs, not calibrated plagiarism probabilities.
This adapter never consumes retrieval scores, gold spans, or expected labels.
Its ranges point to the exact original pair strings, not whole-document reuse.
Numeric-inventory and same-bag guards are conservative vetoes, not general
quantity/entity-role resolution. Spelled-out numbers, coreference, and role
changes with different vocabulary still require model validation and review.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import heapq
import math
import re
import unicodedata
from typing import Any, Mapping, Protocol, Sequence


POLICY = "BIDIRECTIONAL_SENTENCE_NLI_V1"
_LABELS = ("entailment", "neutral", "contradiction")
_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")
_WORDS = re.compile(r"\b\w+\b", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)|\n+")
_NUMBERS = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:%)?")
_MAX_INPUT_CHARS_PER_SIDE = 20_000
_MAX_SENTENCES_PER_SIDE = 64
_MAX_SELECTED_SEGMENT_PAIRS = 64
_MAX_INPUT_PAIRS = 2048
_MAX_DIRECTIONAL_PAIRS = 4096
_MAX_NUMBER_EXCLUSIONS_PER_SIDE = 64
_SINGLE_NUMERIC_MARKER = re.compile(r"\[[0-9]+\]")
_VALUE_CONTEXT = re.compile(
    r"\b(?:array|index|value|score|measurement|matrix|vector|tensor|label|"
    r"mảng|chỉ số|giá trị|điểm|phép đo)\b[^.!?\n]{0,24}$", re.IGNORECASE,
)
_FOLLOWING_UNIT = re.compile(
    r"\s*(?:%|°[CF]|(?:mg|kg|g|mm|cm|km|m|ms|s|sec|seconds?|minutes?|hours?|"
    r"Hz|kHz|MHz|GB|MB|KB|bytes?|tokens?|samples?|reports?|"
    r"độ|giây|phút|giờ|mẫu|tệp|báo cáo)\b)", re.IGNORECASE,
)


class NliScorer(Protocol):
    metadata: dict[str, Any]

    def predict_relations(
        self, pairs: Sequence[tuple[str, str]],
    ) -> Sequence[Mapping[str, Any]]:
        """Return three probabilities or an explicit unsupported-input row."""


@dataclass(frozen=True)
class _Sentence:
    text: str
    start: int
    end: int


def _sentences(text: str, *, limit: int = _MAX_SENTENCES_PER_SIDE + 1) -> list[_Sentence]:
    output: list[_Sentence] = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        raw = text[start:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if left < right:
            output.append(_Sentence(raw[left:right], start + left, start + right))
            if len(output) >= limit:
                return output
        start = end
    raw = text[start:]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    if left < right:
        output.append(_Sentence(raw[left:right], start + left, start + right))
    return output


def _context_windows(text: str, sentences: list[_Sentence], maximum: int) -> list[_Sentence]:
    """One or two contiguous sentences, with original-string character ranges."""
    windows = list(sentences)
    if maximum == 2:
        windows.extend(_Sentence(text[a.start:b.end], a.start, b.end)
                       for a, b in zip(sentences, sentences[1:]))
    return windows


def is_safe_single_numeric_marker(text: str, start: Any, end: Any) -> bool:
    """Check local shape/context, never whether a reference is valid.

    Callers must independently prove the marker links to a unique bibliography
    entry. Reject obvious array/value/operator/unit usages even if the same
    integer happens to exist in that bibliography.
    """
    if (not isinstance(text, str) or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(text)
            or _SINGLE_NUMERIC_MARKER.fullmatch(text[start:end]) is None):
        return False
    before, after = text[:start], text[end:]
    if before and (before[-1].isalnum() or before[-1] in "_])"):
        return False
    if before.rstrip().endswith(("=", "+", "-", "*", "/", "[")):
        return False
    if re.match(r"\s*(?:=|:=|==|!=|<=|>=|[+*/−–-]|\])", after):
        return False
    if _VALUE_CONTEXT.search(before[-64:]) or _FOLLOWING_UNIT.match(after):
        return False
    return True


def _number_exclusion_hints(
    pairs: Sequence[tuple[str, str]], supplied: Any,
) -> list[dict[str, list[dict[str, Any]]]]:
    if supplied is None:
        return [{"report": [], "source": []} for _ in pairs]
    if not isinstance(supplied, Sequence) or isinstance(supplied, (str, bytes)) or len(supplied) != len(pairs):
        raise ValueError("Number-exclusion hints must align exactly with input pairs")
    output: list[dict[str, list[dict[str, Any]]]] = []
    for pair, hints in zip(pairs, supplied, strict=True):
        if not isinstance(hints, Mapping) or set(hints) != {"report", "source"}:
            raise ValueError("Number-exclusion hints require only report/source ranges")
        checked: dict[str, list[dict[str, Any]]] = {}
        for leg, text in zip(("report", "source"), pair, strict=True):
            ranges = hints[leg]
            if (not isinstance(ranges, Sequence) or isinstance(ranges, (str, bytes))
                    or len(ranges) > _MAX_NUMBER_EXCLUSIONS_PER_SIDE):
                raise ValueError("Number-exclusion ranges exceed the bounded list contract")
            values: list[dict[str, Any]] = []
            for item in ranges:
                if not isinstance(item, Mapping) or set(item) != {"start", "end"}:
                    raise ValueError("Number-exclusion range must contain only start/end")
                start, end = item["start"], item["end"]
                if not is_safe_single_numeric_marker(text, start, end):
                    raise ValueError("Number-exclusion range is not a safe single numeric marker")
                values.append({"start": start, "end": end,
                               "marker_sha256": hashlib.sha256(text[start:end].encode()).hexdigest()})
            values.sort(key=lambda row: (row["start"], row["end"]))
            if any(a["end"] > b["start"] for a, b in zip(values, values[1:])):
                raise ValueError("Number-exclusion ranges must not overlap or repeat")
            checked[leg] = values
        output.append(checked)
    return output


def _numeric_inventory(
    text: str, *, offset: int = 0,
    exclusions: Sequence[Mapping[str, Any]] = (),
) -> Counter[str]:
    values: Counter[str] = Counter()
    for match in _NUMBERS.finditer(text):
        if any(offset <= item["start"] and item["end"] <= offset + len(text)
               and item["start"] <= offset + match.start()
               and offset + match.end() <= item["end"] for item in exclusions):
            continue
        raw = match.group()
        suffix = "%" if raw.endswith("%") else ""
        number = raw.removesuffix("%")
        # Commas are locale-ambiguous; retain them instead of guessing whether
        # they denote decimals or thousands. A disagreement causes abstention.
        try:
            normalized = str(Decimal(number).normalize()) if "," not in number else number
        except InvalidOperation:
            normalized = number
        values[normalized + suffix] += 1
    return values


def _checked_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ValueError("NLI prediction must be an object")
    if row.get("supported") is False:
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("Unsupported NLI input requires a reason")
        return {"supported": False, "reason": reason,
                **{key: row[key] for key in ("tokens", "max_length") if key in row}}
    scores: dict[str, Any] = {"supported": True}
    for label in _LABELS:
        value = row.get(label)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("NLI prediction requires three numeric probabilities")
        if not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
            raise ValueError("NLI probability must be finite and in [0, 1]")
        scores[label] = float(value)
    if not math.isclose(sum(scores[label] for label in _LABELS), 1.0, abs_tol=1e-5):
        raise ValueError("NLI probabilities must sum to one")
    if "tokens" in row:
        scores["tokens"] = row["tokens"]
    return scores


class TransformersNliScorer:
    """Local, immutable-checkpoint sequence classifier with no truncation.

    Models are loaded only when this opt-in adapter is constructed. Download
    separately; production inference defaults to local files and safe tensors.
    """

    def __init__(
        self, model: str, revision: str, *, device: str = "cpu", batch_size: int = 8,
        max_length: int = 512, local_files_only: bool = True,
    ) -> None:
        if not isinstance(model, str) or not model:
            raise ValueError("NLI model must be nonempty")
        if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
            raise ValueError("NLI revision must be an immutable commit SHA")
        if not isinstance(device, str) or re.fullmatch(r"cpu|mps|cuda(?::\d+)?", device) is None:
            raise ValueError("NLI device must be explicit")
        for key, value in (("batch_size", batch_size), ("max_length", max_length)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"NLI {key} must be a positive integer")
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        self._torch = torch
        self._device = device
        self._batch_size = batch_size
        self._max_length = max_length
        self._tokenizer = AutoTokenizer.from_pretrained(
            model, revision=revision, local_files_only=local_files_only,
            trust_remote_code=False,
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model, revision=revision, local_files_only=local_files_only,
            trust_remote_code=False, use_safetensors=True,
            **({"dtype": torch.float32} if device in {"cpu", "mps"} else {}),
        ).to(device)
        self._model.eval()
        mapping = {int(key): str(value).casefold()
                   for key, value in self._model.config.id2label.items()}
        if set(mapping.values()) != set(_LABELS) or set(mapping) != {0, 1, 2}:
            raise ValueError("NLI checkpoint must explicitly map entailment/neutral/contradiction")
        self._mapping = mapping
        self.metadata = {
            "backend": "transformers_bidirectional_nli", "model": model,
            "revision": revision, "device": device, "batch_size": batch_size,
            "requested_dtype": "float32" if device in {"cpu", "mps"} else "checkpoint_default",
            "max_length": max_length, "local_files_only": local_files_only,
            "label_mapping": mapping, "truncation": "NEVER_ABSTAIN_OVER_LIMIT",
            "input_chars_per_side_limit": _MAX_INPUT_CHARS_PER_SIDE,
            "directional_pairs_per_call_limit": _MAX_DIRECTIONAL_PAIRS,
            "score_calibration_status": "UNCALIBRATED",
        }

    def predict_relations(self, pairs: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
        checked = _validate_pairs(pairs)
        if len(checked) > _MAX_DIRECTIONAL_PAIRS:
            raise ValueError("NLI directional-pair batch exceeds the hard limit")
        output: list[dict[str, Any] | None] = [None] * len(checked)
        supported: list[tuple[int, tuple[str, str], int]] = []
        for index, pair in enumerate(checked):
            if max(len(pair[0]), len(pair[1])) > _MAX_INPUT_CHARS_PER_SIDE:
                output[index] = {"supported": False, "reason": "NLI_INPUT_CHARACTER_BUDGET_EXCEEDED"}
                continue
            encoded = self._tokenizer(pair[0], pair[1], truncation=False, padding=False)
            tokens = len(encoded["input_ids"])
            if tokens > self._max_length:
                output[index] = {"supported": False, "reason": "NLI_INPUT_TOO_LONG",
                                 "tokens": tokens, "max_length": self._max_length}
            else:
                supported.append((index, pair, tokens))
        for start in range(0, len(supported), self._batch_size):
            batch = supported[start:start + self._batch_size]
            encoded = self._tokenizer(
                [row[1][0] for row in batch], [row[1][1] for row in batch],
                truncation=False, padding=True, return_tensors="pt",
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with self._torch.inference_mode():
                logits = self._model(**encoded).logits
                if tuple(logits.shape) != (len(batch), 3) or not self._torch.isfinite(logits).all():
                    raise ValueError("NLI model returned invalid logits")
                probabilities = self._torch.softmax(logits, dim=-1).cpu().tolist()
            for (index, _, tokens), values in zip(batch, probabilities, strict=True):
                output[index] = {"supported": True, "tokens": tokens,
                                 **{self._mapping[i]: float(value) for i, value in enumerate(values)}}
        assert all(row is not None for row in output)
        return [_checked_row(row) for row in output]


def _validate_pairs(pairs: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    checked: list[tuple[str, str]] = []
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)):
        raise ValueError("NLI inputs must be a sequence of text pairs")
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2 or any(not isinstance(value, str) for value in pair):
            raise ValueError("NLI inputs must contain two strings")
        checked.append((pair[0], pair[1]))
    return checked


class BidirectionalNliVerifier:
    """Verify selected sentence pairs with a conservative abstaining policy."""

    def __init__(
        self, scorer: NliScorer, *, entailment_threshold: float = 0.85,
        rejection_threshold: float = 0.85, margin: float = 0.20,
        max_sentence_pairs: int = 12, min_sentence_words: int = 5,
        max_context_sentences: int = 1,
    ) -> None:
        for name, value in (("entailment_threshold", entailment_threshold),
                            ("rejection_threshold", rejection_threshold), ("margin", margin)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 < value < 1:
                raise ValueError(f"NLI {name} must be in (0, 1)")
        for name, value in (("max_sentence_pairs", max_sentence_pairs), ("min_sentence_words", min_sentence_words)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"NLI {name} must be a positive integer")
        if max_sentence_pairs > _MAX_SELECTED_SEGMENT_PAIRS:
            raise ValueError("NLI selected segment-pair budget exceeds the hard limit")
        if type(max_context_sentences) is not int or max_context_sentences not in {1, 2}:
            raise ValueError("NLI max_context_sentences must be 1 or 2")
        self._scorer = scorer
        self._entailment = float(entailment_threshold)
        self._rejection = float(rejection_threshold)
        self._margin = float(margin)
        self._max_pairs = max_sentence_pairs
        self._min_words = min_sentence_words
        self._context_sentences = max_context_sentences
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.metadata = {
            "policy": POLICY, "scorer": deepcopy(scorer.metadata),
            "entailment_threshold": self._entailment,
            "rejection_threshold": self._rejection, "margin": self._margin,
            "max_sentence_pairs": max_sentence_pairs, "min_sentence_words": min_sentence_words,
            "max_context_sentences": max_context_sentences,
            "comparison_unit": "CONTIGUOUS_SENTENCE_WINDOWS",
            "hard_limits": {"input_chars_per_side": _MAX_INPUT_CHARS_PER_SIDE,
                            "sentences_per_side": _MAX_SENTENCES_PER_SIDE,
                            "selected_segment_pairs": _MAX_SELECTED_SEGMENT_PAIRS,
                            "input_pairs_per_call": _MAX_INPUT_PAIRS,
                            "directional_pairs_per_call": _MAX_DIRECTIONAL_PAIRS,
                            "number_exclusions_per_side": _MAX_NUMBER_EXCLUSIONS_PER_SIDE},
            "over_budget_policy": "ABSTAIN_WITHOUT_SCORING_OR_TRUNCATION",
            "conservative_vetoes": ["IDENTICAL_SEGMENTS_DEFER_TO_EXACT_POLICY",
                                    "NUMERIC_INVENTORY_DISAGREEMENT_INCLUDING_ONE_SIDED",
                                    "SAME_WORD_MULTISET_DIFFERENT_ORDER"],
            "semantic_limitations": [
                "Numeric inventories do not establish which quantity belongs to which entity.",
                "Word-multiset veto is not general role/coreference resolution and may abstain on valid reordering.",
                "NLI model outputs are not independent evidence of copying or calibrated probabilities.",
            ],
            "score_calibration_status": "UNCALIBRATED", "supports_summary": False,
            "evidence_scope": "COMPARED_SENTENCE_SPANS_ONLY", "gold_used": False,
            "supports_explicit_number_exclusion_hints": True,
            "number_exclusion_authority": "CALLER_PROVES_UNIQUE_BIBLIOGRAPHY_LINK",
            "academic_citation_validity": "NOT_ASSESSED",
        }

    def _positive(self, row: Mapping[str, Any]) -> bool:
        return bool(row["supported"] and row["entailment"] >= self._entailment
                    and row["entailment"] - max(row["neutral"], row["contradiction"]) >= self._margin)

    def _negative(self, row: Mapping[str, Any]) -> bool:
        return bool(row["supported"] and max(row["neutral"], row["contradiction"]) >= self._rejection
                    and max(row["neutral"], row["contradiction"]) - row["entailment"] >= self._margin)

    def verify_pairs(
        self, pairs: Sequence[tuple[str, str]], *,
        number_exclusion_ranges: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        checked = _validate_pairs(pairs)
        if len(checked) > _MAX_INPUT_PAIRS:
            raise ValueError("NLI input-pair batch exceeds the hard limit")
        exclusion_hints = _number_exclusion_hints(checked, number_exclusion_ranges)
        preparations: list[tuple[list[tuple[_Sentence, _Sentence]], int, str | None]] = []
        missing: list[tuple[str, str]] = []
        pending: set[tuple[str, str]] = set()
        for report, source in checked:
            if max(len(report), len(source)) > _MAX_INPUT_CHARS_PER_SIDE:
                preparations.append(([], 0, "INPUT_CHARACTER_BUDGET_EXCEEDED"))
                continue
            report_sentences, source_sentences = _sentences(report), _sentences(source)
            if max(len(report_sentences), len(source_sentences)) > _MAX_SENTENCES_PER_SIDE:
                preparations.append(([], 0, "INPUT_SENTENCE_BUDGET_EXCEEDED"))
                continue
            report_windows = _context_windows(report, report_sentences, self._context_sentences)
            source_windows = _context_windows(source, source_sentences, self._context_sentences)
            report_terms = {(a.start, a.end): {x.casefold() for x in _WORDS.findall(a.text)}
                            for a in report_windows}
            source_terms = {(b.start, b.end): {x.casefold() for x in _WORDS.findall(b.text)}
                            for b in source_windows}
            def ordering(item: tuple[_Sentence, _Sentence]) -> tuple[float, int, int]:
                a, b = item
                left, right = report_terms[(a.start, a.end)], source_terms[(b.start, b.end)]
                overlap = len(left & right) / max(1, len(left | right))
                return -overlap, a.start, b.start
            # At most127 windows/side. Stream their cross-product through a
            # bounded heap; never allocate N*M text-pair objects before the cap.
            total = len(report_windows) * len(source_windows)
            selected = heapq.nsmallest(
                self._max_pairs, ((a, b) for a in report_windows for b in source_windows),
                key=ordering,
            )
            preparations.append((selected, total, None))
            for a, b in selected:
                if min(len(_WORDS.findall(a.text)), len(_WORDS.findall(b.text))) < self._min_words:
                    continue
                for pair in ((a.text, b.text), (b.text, a.text)):
                    if pair not in self._cache and pair not in pending:
                        missing.append(pair)
                        pending.add(pair)
        if len(missing) > _MAX_DIRECTIONAL_PAIRS:
            # Withhold the whole batch, rather than silently privileging the
            # first candidates or spilling inference beyond the bounded budget.
            preparations = [([], 0, "DIRECTIONAL_PAIR_BUDGET_EXCEEDED") for _ in checked]
            missing = []
        if missing:
            rows = self._scorer.predict_relations(missing)
            if len(rows) != len(missing):
                raise ValueError("NLI scorer returned the wrong number of predictions")
            validated = [_checked_row(row) for row in rows]
            self._cache.update(zip(missing, validated, strict=True))
        output: list[dict[str, Any]] = []
        for (report, source), (selected, total, budget_reason), hints in zip(
            checked, preparations, exclusion_hints, strict=True,
        ):
            comparisons: list[dict[str, Any]] = []
            for a, b in selected:
                entry: dict[str, Any] = {"report_range": {"start": a.start, "end": a.end},
                                         "source_range": {"start": b.start, "end": b.end}}
                if min(len(_WORDS.findall(a.text)), len(_WORDS.findall(b.text))) < self._min_words:
                    entry.update({"equivalent": False, "rejected": False, "reason": "SEGMENT_TOO_SHORT"})
                else:
                    forward = self._cache[(a.text, b.text)]
                    reverse = self._cache[(b.text, a.text)]
                    numbers_a = _numeric_inventory(a.text, offset=a.start, exclusions=hints["report"])
                    numbers_b = _numeric_inventory(b.text, offset=b.start, exclusions=hints["source"])
                    mismatch = numbers_a != numbers_b
                    def canonical(text):
                        return " ".join(unicodedata.normalize("NFC", text).casefold().split())
                    identical = canonical(a.text) == canonical(b.text)
                    words_a = [x.casefold() for x in _WORDS.findall(unicodedata.normalize("NFC", a.text))]
                    words_b = [x.casefold() for x in _WORDS.findall(unicodedata.normalize("NFC", b.text))]
                    role_ambiguous = words_a != words_b and Counter(words_a) == Counter(words_b)
                    equivalent = (self._positive(forward) and self._positive(reverse)
                                  and not mismatch and not identical and not role_ambiguous)
                    rejected = (self._negative(forward) and self._negative(reverse)
                                and not identical and not role_ambiguous)
                    entry.update({"forward": deepcopy(forward), "reverse": deepcopy(reverse),
                                  "equivalent": equivalent, "rejected": rejected,
                                  "reason": ("IDENTICAL_SEGMENTS_REQUIRE_EXACT_POLICY" if identical else
                                             "WORD_ORDER_ROLE_BINDING_UNRESOLVED" if role_ambiguous else
                                             "NUMERIC_DISAGREEMENT" if mismatch else
                                             "MUTUAL_ENTAILMENT" if equivalent else
                                             "BIDIRECTIONAL_NON_EQUIVALENCE" if rejected else
                                             "UNSUPPORTED_INPUT" if not forward["supported"] or not reverse["supported"] else
                                             "NLI_UNCERTAIN_OR_DIRECTIONAL")})
                entry["number_exclusion_ranges"] = {
                    leg: [deepcopy(item) for item in hints[leg]
                          if sentence.start <= item["start"] and item["end"] <= sentence.end]
                    for leg, sentence in (("report", a), ("source", b))
                }
                comparisons.append(entry)
            positive = [entry for entry in comparisons if entry["equivalent"]]
            complete = bool(total and len(selected) == total)
            all_rejected = complete and all(entry["rejected"] for entry in comparisons)
            if positive:
                best = max(positive, key=lambda row: min(row["forward"]["entailment"], row["reverse"]["entailment"]))
                decision, label, reasons = "PARAPHRASE_SUPPORTED", "PARAPHRASE", ["MUTUAL_SENTENCE_ENTAILMENT"]
                evidence = [deepcopy(best)]
            elif all_rejected:
                decision, label, reasons = "NOT_EQUIVALENT", "NONE", ["ALL_COMPARED_SEGMENTS_NON_EQUIVALENT"]
                evidence = []
            else:
                decision, label = "ABSTAIN", None
                reasons = ([budget_reason] if budget_reason else
                           sorted({entry["reason"] for entry in comparisons}) or ["NO_USABLE_SENTENCE"])
                if not complete and total:
                    reasons.append("SENTENCE_PAIR_BUDGET_EXHAUSTED")
                evidence = []
            output.append({"policy": POLICY, "similarity_type": label, "decision": decision,
                           "reason_codes": reasons, "evidence": evidence, "comparisons": comparisons,
                           "comparison_count": len(selected), "total_sentence_pairs": total,
                           "comparison_complete": complete, "score_calibration_status": "UNCALIBRATED",
                           "max_context_sentences": self._context_sentences,
                           "number_exclusion_policy": ("LINKED_SINGLE_NUMERIC_MARKERS"
                                                       if number_exclusion_ranges is not None else "NONE"),
                           "number_exclusion_ranges": deepcopy(hints),
                           "academic_citation_validity": "NOT_ASSESSED",
                           "evidence_scope": "COMPARED_SENTENCE_SPANS_ONLY",
                           "report_text_sha256": hashlib.sha256(report.encode()).hexdigest(),
                           "source_text_sha256": hashlib.sha256(source.encode()).hexdigest()})
        return output


def load_semantic_verifier(
    model_config: Mapping[str, Any], policy_config: Mapping[str, Any],
) -> BidirectionalNliVerifier | None:
    """Construct the explicitly enabled, offline NLI verifier from locked config.

    ``model_config`` is the semantic-verifier entry itself, not the container
    holding Dense/relevance models. No download or substitute model is allowed.
    """
    if not isinstance(policy_config, Mapping):
        raise ValueError("Semantic-verification policy must be an object")
    enabled = policy_config.get("enabled", True)
    if type(enabled) is not bool:
        raise ValueError("Semantic-verification enabled must be boolean")
    if not enabled:
        return None
    policy_keys = {"enabled", "entailment_threshold", "rejection_threshold", "margin",
                   "max_sentence_pairs", "min_sentence_words", "max_context_sentences",
                   "citation_number_guard"}
    if set(policy_config) - policy_keys:
        raise ValueError("Unknown semantic-verification policy field")
    citation_guard = policy_config.get("citation_number_guard", "NONE")
    if not isinstance(citation_guard, str) or citation_guard not in {"NONE", "LINKED_SINGLE_NUMERIC_MARKERS"}:
        raise ValueError("Unsupported citation number guard policy")
    if not isinstance(model_config, Mapping) or model_config.get("backend") != "transformers_nli":
        raise ValueError("Semantic-verifier backend must be transformers_nli")
    allowed = {"backend", "model", "revision", "device", "batch_size", "max_length"}
    if set(model_config) - allowed or not {"model", "revision"} <= set(model_config):
        raise ValueError("Semantic-verifier requires a locked model configuration")
    scorer = TransformersNliScorer(
        model_config["model"], model_config["revision"],
        device=model_config.get("device", "cpu"), batch_size=model_config.get("batch_size", 8),
        max_length=model_config.get("max_length", 512), local_files_only=True,
    )
    verifier = BidirectionalNliVerifier(
        scorer, **{key: value for key, value in policy_config.items()
                   if key not in {"enabled", "citation_number_guard"}},
    )
    verifier.metadata["citation_number_guard"] = citation_guard
    return verifier
