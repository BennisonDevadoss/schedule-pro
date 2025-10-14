from langchain_chroma import Chroma

from .base_vector_db import BaseVectorService


class ChromaVectorService(BaseVectorService):
    def get_vector_store(self) -> Chroma:
        return Chroma(
            embedding_function=self.embedding_model,
            collection_name=self.collection_name,
            persist_directory="./chroma_db",
        )
