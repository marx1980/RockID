from services.evaluator.metrics import CaseResult, top_k_accuracy, confident_error_rate

def test_metrics():
    rows=[CaseResult("quartz",["quartz","calcite"]),CaseResult("calcite",["quartz","calcite"])]
    assert top_k_accuracy(rows,1)==0.5
    assert top_k_accuracy(rows,3)==1.0
    assert confident_error_rate(rows)==0.5
