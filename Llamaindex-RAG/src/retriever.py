def retrieve_similar_incidents(index, query, top_k=3):

    retriever = index.as_retriever(
        similarity_top_k=top_k
    )

    results = retriever.retrieve(query)

    return results