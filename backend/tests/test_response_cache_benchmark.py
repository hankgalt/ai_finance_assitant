from ai_finance_assistant.response_cache.benchmark import benchmark


def test_benchmark_reconciles_model_calls_and_evidence() -> None:
    report = benchmark(sample_count=2, model_delay_milliseconds=0.0)
    scenarios = {item.scenario: item for item in report.scenarios}

    assert scenarios["cache_disabled"].route_model_calls == 2
    assert scenarios["cache_disabled"].generation_model_calls == 2
    assert scenarios["exact_hit"].route_model_calls == 0
    assert scenarios["exact_hit"].generation_model_calls == 0
    assert scenarios["semantic_hit"].route_model_calls == 2
    assert scenarios["semantic_hit"].generation_model_calls == 0
    assert scenarios["near_miss"].route_model_calls == 2
    assert scenarios["near_miss"].generation_model_calls == 2
    assert all(item.answer_equivalent for item in report.scenarios)
    assert all(item.citations_equivalent for item in report.scenarios)
