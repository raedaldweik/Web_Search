from news_mcp_server.config import _split_list


def test_split_list_basic():
    assert _split_list("a.com, b.com") == ["a.com", "b.com"]


def test_split_list_handles_newlines_and_blanks():
    assert _split_list("a.com\n\n b.com ,") == ["a.com", "b.com"]


def test_split_list_strips_scheme_path_and_wildcards():
    # www. is stripped so a configured "www.gov.ae" / full URL still matches a
    # candidate host normalised to "gov.ae" (regression: otherwise the allow
    # list would silently match nothing).
    assert _split_list("https://www.gov.ae/news") == ["gov.ae"]
    assert _split_list("www.gov.ae") == ["gov.ae"]
    assert _split_list("*.gov.ae") == ["gov.ae"]


def test_split_list_dedupes_preserving_order():
    assert _split_list("a.com, b.com, a.com") == ["a.com", "b.com"]


def test_split_list_empty():
    assert _split_list("") == []
