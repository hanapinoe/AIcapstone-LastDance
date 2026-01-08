import re
import json
from Backend.app.utils.llm_gateway import generate_text
from fastapi import HTTPException


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
        self.query = query

    @staticmethod
    def _heuristic_extract(query: str) -> dict:
        """Best-effort fallback when LLM output cannot be parsed.

        Only extracts information that is explicitly present as simple keywords.
        This avoids returning a totally random RAG list when parsing fails.
        """

        q = (query or "").lower()
        out = {"health_status": "", "taste": "", "context": "", "category": ""}

        # Category: infer only from explicit cues.
        drink_cues = ("uống", "cafe", "cà phê", "trà",
                      "sinh tố", "nước ép", "nước", "sữa")
        food_cues = ("ăn", "phở", "bún", "cơm", "bánh", "cháo", "mì")
        is_drink = any(cue in q for cue in drink_cues)
        is_food = any(cue in q for cue in food_cues)
        if is_drink and not is_food:
            out["category"] = "thức uống"
        elif is_food and not is_drink:
            out["category"] = "món ăn"

        # Context: simple, explicit phrases only.
        ctx_parts = []
        if "sáng" in q:
            ctx_parts.append("buổi sáng")
        if "trưa" in q:
            ctx_parts.append("buổi trưa")
        if "chiều" in q:
            ctx_parts.append("buổi chiều")
        if "tối" in q or "đêm" in q:
            ctx_parts.append("buổi tối")
        if "lạnh" in q:
            ctx_parts.append("trời lạnh")
        if "nóng" in q:
            ctx_parts.append("trời nóng")
        if "mưa" in q:
            ctx_parts.append("trời mưa")
        if "sau khi" in q and ("tập" in q or "thể thao" in q):
            ctx_parts.append("sau khi tập thể thao")

        if ctx_parts:
            # de-dup while preserving order
            seen = set()
            uniq = []
            for p in ctx_parts:
                if p not in seen:
                    uniq.append(p)
                    seen.add(p)
            out["context"] = ", ".join(uniq)

        return out

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
                    Bạn là AI trích xuất thông tin có cấu trúc từ truy vấn ăn/uống.

                    Hãy ưu tiên trả về một JSON object hợp lệ.
                    (Nếu có thêm vài chữ dẫn/giải thích thì vẫn được, nhưng nhớ đảm bảo trong câu trả lời có đúng 1 JSON object để hệ thống trích ra.)

                    Định nghĩa:
                    - health_status: chỉ điền khi người dùng nói rõ bệnh/tình trạng sức khỏe (vd: "cholesterol cao", "tiểu đường").
                    - taste: chỉ điền khi người dùng nói rõ sở thích hương vị (vd: "ngọt", "đắng", "ít đường").
                    - context: chỉ điền khi người dùng nói rõ bối cảnh/thời điểm/thời tiết/hoạt động (vd: "buổi sáng", "trời lạnh", "sau khi tập thể thao").
                    - category: chỉ được là một trong 3 giá trị: "món ăn", "thức uống", "".
                      - Nếu truy vấn có từ “uống” hoặc nêu đồ uống rõ ràng (vd: cafe, trà, sinh tố) → category="thức uống".
                      - Nếu truy vấn có từ “ăn” hoặc nêu món ăn rõ ràng (vd: phở, bún) → category="món ăn".
                      - Nếu không rõ → category="".

                    Quy tắc:
                    - Nếu không được nhắc tới → để "".
                    - Không suy đoán / không bịa thêm thông tin.
                    - Không diễn đạt lại truy vấn.
                    - Nếu bạn có thêm chữ ngoài JSON, vui lòng tránh dùng ký tự "{" hoặc "}" ở phần chữ đó.

                    Ví dụ 1:
                    Input: "sáng nay tôi muốn uống cafe, trời khá là lạnh"
                    Output:
                    {"health_status":"","taste":"","context":"buổi sáng, trời lạnh","category":"thức uống"}

                    Ví dụ 2:
                    Input: "tôi bị cholesterol cao"
                    Output:
                    {"health_status":"cholesterol cao","taste":"","context":"","category":""}
                    """
                )
            },
            {
                "role": "user",
                "content": f"Truy vấn: {self.query}\nChỉ trả về JSON object đúng định dạng."
            }
        ]

        decoded = generate_text(
            task_type="parsing",
            messages=messages,
            max_new_tokens=256,
            temperature=0.0,
            do_sample=False,
        )

        # Chỉ lấy phần sau "assistant"
        if "assistant" in decoded:
            decoded = decoded.split("assistant", 1)[-1].strip()

        # print("DEBUG CLEAN:", decoded)

        # Parse JSON
        match = re.search(r"\{[\s\S]*\}", decoded)
        if not match:
            fallback = self._heuristic_extract(self.query)
            if fallback.get("category") or fallback.get("context"):
                return fallback
            raise HTTPException(
                status_code=422,
                detail="Không trích xuất được thông tin từ câu hỏi. Bạn hãy nhập lại rõ hơn (vd: muốn ăn/uống gì, bối cảnh, khẩu vị, tình trạng sức khỏe nếu có).",
            )

        try:
            obj = json.loads(match.group())
        except Exception:
            fallback = self._heuristic_extract(self.query)
            if fallback.get("category") or fallback.get("context"):
                return fallback
            raise HTTPException(
                status_code=422,
                detail="Cú pháp kết quả trích xuất bị lỗi. Bạn hãy nhập lại câu hỏi rõ hơn.",
            )

        if not isinstance(obj, dict):
            raise HTTPException(
                status_code=422, detail="Kết quả trích xuất không hợp lệ. Hãy nhập lại câu hỏi.")

        # Normalize + clamp
        keys = ("health_status", "taste", "context", "category")
        out = {}
        for k in keys:
            v = obj.get(k, "")
            out[k] = v if isinstance(v, str) else ""

        if out["category"] not in ("món ăn", "thức uống", ""):
            out["category"] = ""

        return out
