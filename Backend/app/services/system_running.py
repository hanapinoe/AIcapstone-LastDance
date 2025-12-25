from Backend.app.services.infoAgent.extract_fields import ExtractFieldsService
from Backend.app.services.infoAgent.rewrite_query_for_rag import RewriteQueryForRAGService
from Backend.app.services.infoAgent.vectorDB_query import QueryInitializeService
from Backend.app.services.infoAgent.choose_best_option import ChooseBestOptionService

from typing import Any, Dict, List, Optional, Tuple, Type
import json
import random


class infoAgentService:
    """
    Orchestrates the end-to-end process of handling a user query with LLM and R
    AG, including field extraction, query rewriting, RAG retrieval, and option selection.
    Args:
        userQuery (str): The original user query.
        vectorDB_path (str): Path to the vector database for RAG.
        extract_fields_service_cls: Class for extracting fields from the query.
        rewrite_query_service_cls: Class for rewriting the query for RAG.
        query_initialize_service_cls: Class for initializing the RAG retriever.
        choose_best_option_service_cls: Class for choosing the best option based on LLM.
    """

    def __init__(
        self,
        userQuery: str,
        vectorDB_path: str,
        extract_fields_service_cls: Type[Any] = ExtractFieldsService,
        rewrite_query_service_cls: Type[Any] = RewriteQueryForRAGService,
        query_initialize_service_cls: Type[Any] = QueryInitializeService,
        choose_best_option_service_cls: Type[Any] = ChooseBestOptionService,
    ):
        self.user_query = userQuery
        self.vectorDB_path = vectorDB_path
        self._ExtractFieldsService = extract_fields_service_cls
        self._RewriteQueryForRAGService = rewrite_query_service_cls
        self._QueryInitializeService = query_initialize_service_cls
        self._ChooseBestOptionService = choose_best_option_service_cls

    @staticmethod
    def _get_metadata(hit: Any) -> Dict[str, Any]:
        meta = getattr(hit, "metadata", None)
        if isinstance(meta, dict):
            return meta
        node = getattr(hit, "node", None)
        meta2 = getattr(node, "metadata", None)
        if isinstance(meta2, dict):
            return meta2
        return {}

    @staticmethod
    def _get_score(hit: Any) -> Optional[float]:
        return getattr(hit, "score", None)

    @staticmethod
    def _parse_option_json(option_json: Any) -> Dict[str, Any]:
        if option_json is None:
            return {}
        if isinstance(option_json, dict):
            return option_json
        if isinstance(option_json, str):
            s = option_json.strip()
            if not s:
                return {}
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def query_with_llm_and_rag(self, top_k: int = 5) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Handles the full pipeline:
        - Extract fields from the user query using LLM.
        - Rewrite the query for RAG.
        - Retrieve documents using RAG.
        Args:
            top_k (int): Number of top results to return after filtering.
        Returns:
            Tuple[List[Any], Dict[str, Any]]: A tuple containing the list of retrieved documents and extracted fields.
        """
        print("\n=== ORIGINAL QUERY ===")
        print(self.user_query)

        # 1) LLM analyze fields
        fields = self._ExtractFieldsService(self.user_query).extract_fields()
        print("\n=== PARSED FIELDS ===")
        print(fields)

        category = (fields.get("category", "") or "").strip()

        # 2) Rewrite query for RAG
        rewritten = self._RewriteQueryForRAGService(
            fields).rewrite_query_for_rag()
        print("\n=== REWRITTEN QUERY FOR RAG ===")
        print(rewritten)

        # 3) Search RAG
        retriever = self._QueryInitializeService(
            self.vectorDB_path).query_initialize()
        raw_results = retriever.retrieve(rewritten)

        # 4) Filter by category if present
        filtered: List[Any] = []
        for hit in raw_results:
            meta = self._get_metadata(hit)
            item_type = (meta.get("type", "") or "").lower()

            if category:
                c = category.lower()
                if "uống" in c and item_type != "thức uống":
                    continue
                if ("ăn" in c or "món" in c) and item_type != "đồ ăn":
                    continue

            filtered.append(hit)
            if len(filtered) >= top_k:
                break

        print("\n=== RAG RESULTS ===")
        if not filtered:
            print("No dish found matching the category - returning raw top-k")
            filtered = list(raw_results[:top_k])

        # 5) Print list of top-k (DO NOT call choose_best_option here)
        for i, hit in enumerate(filtered):
            meta = self._get_metadata(hit)
            score = self._get_score(hit)
            score_str = f"{score:.4f}" if isinstance(
                score, (float, int)) else "N/A"

            print(f"\n--- Rank {i+1} | score={score_str}")
            print("Name:", meta.get("name"))
            print("Type:", meta.get("type"))
            print("Ingredient:", meta.get("ingredient"))
            print("Option_json:", meta.get("option_json"))

        return filtered, fields

    def pick_random_node_that_llm_can_choose(
        self,
        filtered_nodes: List[Any],
        fields: Dict[str, Any],
        max_try: int = 10,
        seed: Optional[int] = None,
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        From the filtered RAG nodes, randomly pick one and use LLM to choose the best
        option. Repeat up to `max_try` times if LLM fails to provide a valid option.
        Args:
            filtered_nodes (List[Any]): List of filtered RAG nodes.
            fields (Dict[str, Any]): Extracted fields from the user query.
            max_try (int): Maximum number of attempts to pick a valid node.
            seed (Optional[int]): Seed for random number generator for reproducibility.
        Returns:
            Tuple[Optional[Any], Dict[str, Any]]: A tuple containing the selected node (or None) and
            the LLM's recommended options.
        """
        rng = random.Random(seed)

        candidates: List[Any] = []
        for hit in filtered_nodes:
            meta = self._get_metadata(hit)
            option_dict = self._parse_option_json(meta.get("option_json"))
            if option_dict:
                candidates.append(hit)

        if not candidates:
            print("\n=== RANDOM PICK ===")
            print("No item has a valid option_json to randomize.")
            return None, {"recommended_options": {}}

        rng.shuffle(candidates)

        tries = min(max_try, len(candidates))
        for idx in range(tries):
            hit = candidates[idx]
            meta = self._get_metadata(hit)

            base_options = meta.get("option_json", "{}")
            dish_name = meta.get("name", "")
            canonical_description = meta.get("description", "")
            health_profile = meta.get("health_profile", "")
            context_suitability = meta.get("context_suitability", "")

            print("\n=== RANDOM PICK ===")
            print(f"Try {idx+1}/{tries}:", dish_name)

            chooser = self._ChooseBestOptionService(
                fields,
                dish_name,
                base_options,
                canonical_description,
                health_profile,
                context_suitability,
            )
            result = chooser.choose_best_option()

            rec = result.get("recommended_options", {})
            if isinstance(rec, dict) and len(rec) > 0:
                print("LLM recommended_options:", rec)
                return hit, result

            print("SKIP: recommended_options empty")

        print("\n=== RANDOM PICK ===")
        print("All candidates were SKIPped (recommended_options empty).")
        return None, {"recommended_options": {}}
