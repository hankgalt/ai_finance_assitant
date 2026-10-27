"""Read-only retrieval service returning provenance-rich evidence."""

from ai_finance_assistant.knowledge.models import Evidence, RetrievalQuery
from ai_finance_assistant.knowledge.representations import RepresentationEncoder
from ai_finance_assistant.knowledge.store import KnowledgeStore


class KnowledgeRetriever:
    def __init__(self, *, store: KnowledgeStore, encoder: RepresentationEncoder) -> None:
        self._store = store
        self._encoder = encoder

    def retrieve(self, collection_name: str, query: RetrievalQuery) -> tuple[Evidence, ...]:
        dense = self._encoder.embed_dense([query.text])[0]
        sparse = self._encoder.embed_sparse([query.text])[0]
        return self._store.search(collection_name, query, dense, sparse)
