import pytest

from app.kb import load_articles
from app.main import DEFAULT_KB
from app.retriever import Retriever


@pytest.fixture(scope="session")
def articles():
    return load_articles(DEFAULT_KB)


@pytest.fixture(scope="session")
def retriever(articles):
    return Retriever(articles)
