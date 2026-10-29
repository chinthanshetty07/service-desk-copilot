from eval.run_eval import evaluate


def test_offline_eval_meets_quality_gates():
    s = evaluate()["summary"]
    assert s["retrieval_hit@3"] >= 0.9
    assert s["category_accuracy"] >= 0.85
    assert s["abstain_accuracy"] >= 0.9
