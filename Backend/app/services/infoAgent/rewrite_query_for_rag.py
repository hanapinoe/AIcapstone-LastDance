class RewriteQueryForRAGService:
    """
    Rewrite user queries into a normalized Vietnamese phrase for Retrieval-Augmented Generation (RAG).

    The goal is to turn a free-form user question into a compact, search-friendly string built
    from extracted slots (taste/health/context/category/options). This helps the vector search/
    retriever match the most relevant documents.

    Args:
        fields (dict): Structured fields extracted from the user query.
    """

    def __init__(self, fields: dict):
        # Expected keys (depending on ExtractFieldsService):
        # - health_status, taste, context, category, option
        self.fields = fields or {}

    def rewrite_query_for_rag(self):
        """
        Rewrite the user query based on extracted fields.

        Returns:
            str: The rewritten query for RAG.
        """
        # Extract fields safely and normalize whitespace.
        health = self.fields.get("health_status", "").strip()
        taste = self.fields.get("taste", "").strip()
        context = self.fields.get("context", "").strip()
        category = self.fields.get("category", "").strip()
        options = self.fields.get("option", "").strip()

        # Collect query “parts” that will be concatenated into the final rewritten query.
        parts = []

        # Taste preference (e.g., "sweet", "bitter").
        if taste:
            parts.append(f"taste {taste}")

        # Health constraint (e.g., "diabetes", "weight loss").
        if health:
            parts.append(f"good for {health}")

        # Usage context (e.g., "morning", "after gym").
        if context:
            parts.append(f"suitable when {context}")

        # Category normalization: map various synonyms to a canonical label.
        if category:
            c = category.lower()
            if any(kw in c for kw in ["uống", "drink", "thức uống"]):
                parts.append("drink")

            elif any(kw in c for kw in ["ăn", "món", "food", "đồ ăn"]):
                parts.append("food")

        else:
            # Fallback behavior: if category is missing, append `taste` as-is.
            # (Note: `taste` may already have been added above as "vị {taste}".)
            parts.append(taste)

        # Optional explicit user-provided options/choices.
        if options:
            parts.append(f"suggested option {options}")

        # Join using commas to keep chunks separable for retrieval.
        rewritten = ", ".join(parts)
        return rewritten
