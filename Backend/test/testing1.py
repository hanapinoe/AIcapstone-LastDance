import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List


# Allow running this file directly: `python Backend\test\testing1.py`
PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@dataclass
class FakeNode:
    metadata: Dict[str, Any]


@dataclass
class FakeNodeWithScore:
    node: FakeNode
    score: float

    @property
    def metadata(self) -> Dict[str, Any]:
        # Make it compatible with how system_running accesses `node.metadata`
        return self.node.metadata


class FakeExtractFieldsService:
    def __init__(self, query: str):
        self.query = query

    def extract_fields(self) -> Dict[str, str]:
        # Deterministic fake output (no LLM)
        return {
            "health_status": "high cholesterol",
            "taste": "sweet and mild",
            "context": "just finished sports",
            "category": "drink",
        }


class FakeRetriever:
    def retrieve(self, rewritten_query: str) -> List[FakeNodeWithScore]:
        # Deterministic fake RAG hits
        items = [
            {
                "name": "sugarcane juice",
                "type": "drink",
                "ingredient": "sugarcane, ice, salt, kumquat",
                "option_json": '{"ice": ["lots", "less", "none"], "kumquat": ["yes", "no"], "salt": ["yes", "no"]}',
                "description": "Sugarcane juice is a sweet, refreshing drink.",
                "health_profile": "{}",
                "context_suitability": "{}",
            },
            {
                "name": "Pineapple Smoothie",
                "type": "drink",
                "ingredient": "pineapple, condensed milk, ice, sugar",
                "option_json": '{"condensed_milk": ["lots", "less", "none"], "sugar": ["lots", "less", "none"], "ice": ["lots", "less", "none"]}',
                "description": "A sweet and refreshing pineapple smoothie.",
                "health_profile": "{}",
                "context_suitability": "{}",
            },
            {
                "name": "Bread",
                "type": "food",
                "ingredient": "bread, pate",
                "option_json": "{}",
                "description": "Bread is quick and convenient.",
                "health_profile": "{}",
                "context_suitability": "{}",
            },
        ]

        results: List[FakeNodeWithScore] = []
        for i, meta in enumerate(items):
            results.append(FakeNodeWithScore(
                node=FakeNode(metadata=meta), score=0.78 - i * 0.01))
        return results


class FakeQueryInitializeService:
    def __init__(self, vectorDB_path: str):
        self.vectorDB_path = vectorDB_path

    def query_initialize(self) -> FakeRetriever:
        return FakeRetriever()


class FakeChooseBestOptionService:
    def __init__(
        self,
        user_fields: Dict[str, Any],
        dish_name: str,
        base_options: str,
        canonical_description: str,
        health_profile: str,
        context_suitability: str,
    ):
        self.user_fields = user_fields
        self.dish_name = dish_name
        self.base_options = base_options

    def choose_best_option(self) -> Dict[str, Any]:
        # Deterministic fake “LLM choose option” output
        recommended: Dict[str, str] = {}
        if "ice" in self.base_options:
            recommended["ice"] = "less"
        if "sugar" in self.base_options:
            recommended["sugar"] = "less"
        if "salt" in self.base_options:
            recommended["salt"] = "none"
        if "kumquat" in self.base_options:
            recommended["kumquat"] = "no"
        return {"recommended_options": recommended}


def main() -> None:
    from Backend.app.services.system_running import infoAgentService

    query = "tôi vừa mới chơi thể thao về, tôi muốn uống gì đó ngọt và nhẹ, tôi bị cholesteron cao"

    agent = infoAgentService(
        userQuery=query,
        vectorDB_path="./fake_vectordb",
        extract_fields_service_cls=FakeExtractFieldsService,
        query_initialize_service_cls=FakeQueryInitializeService,
        choose_best_option_service_cls=FakeChooseBestOptionService,
    )

    # Still uses the real RewriteQueryForRAGService (no extra LLM calls now)
    results = agent.query_with_llm_and_rag(top_k=1)

    print("\n=== FINAL RESULTS (returned) ===")
    print(results)


if __name__ == "__main__":
    main()
