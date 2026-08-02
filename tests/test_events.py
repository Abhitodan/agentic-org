from agentic_org.core.events import Event


def test_append_and_list(events):
    events.append(Event(event_type="a", payload={"n": 1}))
    events.append(Event(event_type="b", payload={"n": 2}, cost_usd=0.5,
                        tokens_in=10, tokens_out=20))
    listed = events.list()
    assert len(listed) == 2
    assert listed[0]["event_type"] == "b"  # newest first
    assert listed[0]["payload"] == {"n": 2}


def test_hash_chain_valid(events):
    for i in range(5):
        events.append(Event(event_type=f"e{i}"))
    ok, bad = events.verify_chain()
    assert ok and bad is None


def test_tampering_detected(events, conn):
    events.append(Event(event_type="original", payload={"v": 1}))
    events.append(Event(event_type="second"))
    conn.execute("UPDATE events SET payload = '{\"v\": 999}' "
                 "WHERE event_type = 'original'")
    conn.commit()
    ok, bad = events.verify_chain()
    assert not ok
    assert bad is not None


def test_totals(events):
    events.append(Event(event_type="x", workflow_id="wf_1",
                        tokens_in=100, tokens_out=50, cost_usd=0.01))
    events.append(Event(event_type="y", workflow_id="wf_1",
                        tokens_in=200, tokens_out=100, cost_usd=0.02))
    totals = events.totals("wf_1")
    assert totals["tokens_in"] == 300
    assert totals["tokens_out"] == 150
    assert abs(totals["cost_usd"] - 0.03) < 1e-9
