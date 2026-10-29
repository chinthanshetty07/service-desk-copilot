import pytest

from app.kb import load_articles


def test_loads_every_article_with_steps(articles):
    assert len(articles) == 14
    assert all(a.id.startswith("KB-") and a.title and a.category for a in articles)
    password = next(a for a in articles if a.id == "KB-001")
    assert password.automation == "password_reset"
    assert password.steps()[0].startswith("Ask the employee")


def test_rejects_article_without_front_matter(tmp_path):
    (tmp_path / "bad.md").write_text("no header here")
    with pytest.raises(ValueError, match="missing front matter"):
        load_articles(tmp_path)


def test_rejects_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="no articles"):
        load_articles(tmp_path)


@pytest.mark.parametrize(
    "query, expected",
    [
        ("I forgot my password", "KB-001"),
        ("vpn certificate expired", "KB-004"),
        ("printer shows offline", "KB-009"),
        ("someone stole my laptop", "KB-013"),
    ],
)
def test_top_hit_is_the_right_article(retriever, query, expected):
    assert retriever.search(query)[0].article.id == expected


def test_unknown_words_return_no_hits_instead_of_crashing(retriever):
    assert retriever.search("zzqx blorf") == []
    assert retriever.search("") == []


def test_scores_are_sorted_and_bounded(retriever):
    hits = retriever.search("outlook emails missing", k=3)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1.0001 for s in scores)
