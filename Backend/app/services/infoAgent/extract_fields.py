import re
import json
from Backend.app.utils.model_utils import llmInitialize


class ExtractFieldsService:
    """
    Extract structured fields from a free-form user query.

    Intended usage:
    - Send a carefully constrained prompt to a chat/LLM model.
    - Parse the model output as JSON.
    - Return a normalized dict used by downstream services (e.g., query rewriting for RAG).

    Expected output keys:
    - health_status: user health condition/constraint (e.g., "tiểu đường")
    - taste: taste preference (e.g., "ngọt", "đắng")
    - context: usage context (e.g., "buổi chiều", "khi tập gym")
    - category: high-level category (e.g., "món ăn" / "thức uống")

    Notes:
    - If a field is not explicitly mentioned, it should be an empty string.

    Args:
        model: The language model to use for extraction.
        tokenizer: The tokenizer corresponding to the language model.
    """

    def __init__(self, query: str):
        self.model, self.tokenizer = llmInitialize.initialize_LLM()
        self.query = query

    def extract_fields(self) -> dict:
        """
        Extracts fields from the user query using the LLM.

        Returns:
            dict: A dictionary with extracted fields.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    """
                    You are an AI specialized in analyzing user queries and extracting information.

                    Task:
                    - health_status: fill only if the user explicitly mentions a health condition.
                    - taste: fill only if the user explicitly mentions taste preference.
                    - context: fill only if the user explicitly mentions usage context.
                    - category: fill only if the user explicitly indicates food or drink.

                    Rules:
                    - If information is NOT mentioned -> set to "".
                    - DO NOT infer or fabricate information.
                    - DO NOT rephrase the content.
                    - Return only valid JSON.
                    """
                )
            },
            {
                "role": "user",
                "content": f"Query: {self.query}\nReturn JSON."
            }
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(
            prompt, return_tensors="pt").to(self.model.device)

        output = self.model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.0,
            do_sample=False
        )

        decoded = self.tokenizer.decode(
            output[0], skip_special_tokens=True, skip_prompt=True)

        # Chỉ lấy phần sau "assistant"
        if "assistant" in decoded:
            decoded = decoded.split("assistant", 1)[-1].strip()

        # print("DEBUG CLEAN:", decoded)

        # Parse JSON
        match = re.search(r"\{[\s\S]*\}", decoded)
        if not match:
            return {"health_status": "", "taste": "", "context": "", "category": ""}

        try:
            return json.loads(match.group())
        except:
            return {"health_status": "", "taste": "", "context": "", "category": ""}
