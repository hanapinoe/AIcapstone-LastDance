from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from Backend.app.utils.model_utils import embedInitialize
import chromadb


class QueryInitializeService:
    """Initialize the Chroma vector database and build a LlamaIndex retriever.

    This service wires together:
    - ChromaDB (persistent vector storage)
    - ChromaVectorStore (LlamaIndex adapter)
    - VectorStoreIndex (LlamaIndex index wrapper)
    - Retriever (top-k similarity search)

    Args:
        vectorDB_path (str): Filesystem path where Chroma persists data.
        embed_model: Embedding model used by LlamaIndex to embed queries/documents.
            (Type depends on your LlamaIndex embedding integration.)
    """

    def __init__(self, vectorDB_path: str):
        embed_init = embedInitialize()
        self.embed_model = embed_init.initialize_embedModel()
        self.vectorDB_path = vectorDB_path

    def query_initialize(self):
        """
        Initialize ChromaDB and build a LlamaIndex retriever.
        Returns:
            retriever: LlamaIndex retriever for similarity search.
        """
        # Persistent client ensures vectors are stored on disk and reused between runs.
        db = chromadb.PersistentClient(path=self.vectorDB_path)

        # Create or reuse the collection that holds user-preference vectors.
        # HNSW settings control recall/speed tradeoffs for similarity search.
        collection = db.get_or_create_collection(
            name="UserPreference_collection",
            metadata={
                "hnsw:space": "cosine",
                "hnsw:search_ef": 64,
                "hnsw:construction_ef": 150,
                "hnsw:M": 32,
            },
        )

        # Adapter that lets LlamaIndex talk to Chroma collections.
        vector_store = ChromaVectorStore(chroma_collection=collection)

        # Build an index wrapper over the existing vector store.
        # `embed_model` is required for embedding queries consistently.
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=self.embed_model,
        )

        # Retriever will return the top 15 most similar matches.
        retriever = index.as_retriever(similarity_top_k=15)
        return retriever
