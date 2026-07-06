from app.services.search_engine import merge_and_rank
from app.services.search_types import SearchResult


def _result(url, score, title="t", content="c", query="q"):
    return SearchResult(title=title, url=url, content=content, score=score, source_query=query)


def test_deduplicates_by_normalized_url():
    results = [
        _result("https://linkedin.com/in/janedoe/", 0.5),
        _result("https://linkedin.com/in/janedoe", 0.9),  # same URL, no trailing slash, higher score
    ]

    merged = merge_and_rank(results)

    assert len(merged) == 1
    assert merged[0].score == 0.9


def test_ranks_by_score_descending():
    results = [
        _result("https://a.com", 0.3),
        _result("https://b.com", 0.9),
        _result("https://c.com", 0.6),
    ]

    merged = merge_and_rank(results)

    assert [r.url for r in merged] == ["https://b.com", "https://c.com", "https://a.com"]


def test_results_without_url_are_dropped():
    results = [_result("", 0.9), _result("https://a.com", 0.5)]

    merged = merge_and_rank(results)

    assert len(merged) == 1
    assert merged[0].url == "https://a.com"


def test_limit_caps_returned_results():
    results = [_result(f"https://site{i}.com", i) for i in range(20)]

    merged = merge_and_rank(results, limit=5)

    assert len(merged) == 5
    assert merged[0].url == "https://site19.com"
