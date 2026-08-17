"""Recent assistant style fingerprints."""

from mika.conversation.skills.natural_expression.style_ledger import StyleLedger


def test_ledger_tracks_recent_emoji_dashes_and_openings() -> None:
    ledger = StyleLedger()
    ledger.observe("c", "yeah, fair 😭", ())
    ledger.observe("c", "nah — not happening", ())

    snapshot = ledger.snapshot("c")

    assert snapshot.recent_emoji == ("😭",)
    assert snapshot.recent_openings == ("yeah", "nah")
    assert snapshot.dash_ages == (0,)


def test_quotes_code_and_urls_do_not_count_as_dash_style() -> None:
    ledger = StyleLedger()
    ledger.observe("c", 'you said "fine — whatever"', ())
    ledger.observe("c", "`git log --oneline` https://example.com/a--b", ())

    assert ledger.snapshot("c").dash_ages == ()
