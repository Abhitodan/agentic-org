"""Document retrieval: PageIndex trees + vector embeddings."""

from .indexer import DocumentIndexer
from .pageindex import PageIndexStore, build_page_tree, retrieve_from_tree
from .vectors import VectorHit, VectorStore

__all__ = [
    "DocumentIndexer",
    "PageIndexStore",
    "build_page_tree",
    "retrieve_from_tree",
    "VectorHit",
    "VectorStore",
]
