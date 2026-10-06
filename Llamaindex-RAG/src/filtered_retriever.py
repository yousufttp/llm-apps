from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
)


def retrieve_by_category(index, query, category, top_k=3):

    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="category",
                value=category,
            )
        ]
    )

    retriever = index.as_retriever(
        similarity_top_k=top_k,
        filters=filters,
    )

    return retriever.retrieve(query)