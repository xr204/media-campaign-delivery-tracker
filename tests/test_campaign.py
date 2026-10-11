from media_campaign import InfraiClient, opened_event


def test_email_events_extracts_items() -> None:
    client = InfraiClient(api_key="test")
    client._request = lambda *args, **kwargs: {"items": [{"type": "open"}], "total": 1}
    assert client.email_events("message-1") == [{"type": "open"}]


def test_bounce_does_not_count_as_open() -> None:
    events = [{"event": "delivered"}, {"event": "bounce"}]
    assert opened_event(events) is False


def test_open_event_marks_creator_engaged() -> None:
    assert opened_event([{"type": "delivered"}, {"type": "open"}]) is True
