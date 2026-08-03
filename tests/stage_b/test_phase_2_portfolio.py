from local_developer_worker import stage_b_phase_2_portfolio


def test_pb2_06_runner_requires_both_regression_portfolios(monkeypatch):
    monkeypatch.setattr(
        stage_b_phase_2_portfolio,
        "_run_regression_portfolios",
        lambda timeout: {"passed": True, "stage_a_completed": 20, "phase_1_completed": 10},
    )
    monkeypatch.setattr(
        stage_b_phase_2_portfolio,
        "_run_test",
        lambda node, timeout: {
            "test_id": node,
            "run_status": "passed",
            "observed_test_count": 1,
            "evidence_hash": "observed",
        },
    )

    output = stage_b_phase_2_portfolio.run_phase_2_portfolio()

    assert output["portfolio_size"] == 8
    assert output["completed"] == stage_b_phase_2_portfolio.EXPECTED_IDS
    assert output["reconciliation_results"]["stage_a_completed"] == 20
    assert output["reconciliation_results"]["phase_1_completed"] == 10
    assert output["portfolio_acceptance"] == "phase_2_complete"
