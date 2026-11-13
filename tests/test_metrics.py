import pytest

from services.evaluator.metrics import (
    UNKNOWN, CaseResult, confident_error_rate, coverage, expected_calibration_error, macro_f1,
    per_class_recall, report, selective_accuracy, top_k_accuracy, unknown_false_accept_rate,
)


def test_metrics():
    rows = [CaseResult("quartz", ["quartz", "calcite"]), CaseResult("calcite", ["quartz", "calcite"])]
    assert top_k_accuracy(rows, 1) == 0.5
    assert top_k_accuracy(rows, 3) == 1.0
    assert confident_error_rate(rows) == 0.5


def test_abstention_counts_as_miss_but_not_as_confident_error():
    rows = [CaseResult("quartz", ["quartz"]), CaseResult("calcite", ["quartz"], abstained=True)]
    assert top_k_accuracy(rows, 1) == 0.5
    assert coverage(rows) == 0.5
    assert selective_accuracy(rows) == 1.0
    assert confident_error_rate(rows) == 0.0


def test_accepted_labels_count_as_correct():
    rows = [CaseResult("rock.marble", ["min.calcite"], accepted=frozenset({"min.calcite"}))]
    assert top_k_accuracy(rows, 1) == 1.0


def test_ood_cases():
    rows = [
        CaseResult(UNKNOWN, ["min.quartz"]),  # false accept
        CaseResult(UNKNOWN, ["min.quartz"], abstained=True),
        CaseResult("min.quartz", ["min.quartz"]),
    ]
    assert unknown_false_accept_rate(rows) == 0.5
    assert top_k_accuracy(rows, 1) == 1.0  # OOD excluded from accuracy
    assert confident_error_rate(rows) == 0.5  # answered OOD counts as an error


def test_confident_error_threshold():
    rows = [CaseResult("a", ["b"], confidence=0.9), CaseResult("a", ["b"], confidence=0.3)]
    assert confident_error_rate(rows, min_confidence=0.8) == 1.0
    assert confident_error_rate(rows, min_confidence=0.95) == 0.0


def test_macro_f1_and_recall():
    rows = [
        CaseResult("a", ["a"]), CaseResult("a", ["b"]),
        CaseResult("b", ["b"]), CaseResult("b", ["b"]),
    ]
    assert per_class_recall(rows) == {"a": 0.5, "b": 1.0}
    # a: p=1, r=.5, f1=2/3 ; b: p=2/3, r=1, f1=.8
    assert macro_f1(rows) == pytest.approx((2 / 3 + 0.8) / 2)


def test_ece():
    perfect = [CaseResult("a", ["a"], confidence=1.0), CaseResult("a", ["b"], confidence=0.0)]
    assert expected_calibration_error(perfect) == 0.0
    over = [CaseResult("a", ["b"], confidence=0.95)]
    assert expected_calibration_error(over) == pytest.approx(0.95)


def test_report_keys():
    assert set(report([CaseResult("a", ["a"])])) >= {"top1", "top3", "macro_f1", "ece", "coverage"}


def test_ranked_accuracy_ignores_abstention():
    from services.evaluator.metrics import category_accuracy, ranked_accuracy
    rows = [CaseResult("min.a", ["min.a", "min.b"], abstained=True), CaseResult("min.b", ["rock.c", "min.b"])]
    assert ranked_accuracy(rows, 1) == 0.5 and ranked_accuracy(rows, 2) == 1.0
    assert top_k_accuracy(rows, 1) == 0.0
    assert category_accuracy(rows) == 0.5
