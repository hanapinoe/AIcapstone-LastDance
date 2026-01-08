import json
import re
from textwrap import dedent

from Backend.app.utils.llm_gateway import generate_text


class ExplainationService:
    def __init__(self, parsing_prompt, dish_name, dish_type, recommended_options):
        self.parsing_prompt = parsing_prompt
        self.dish_name = dish_name
        self.dish_type = dish_type
        self.recommended_options = recommended_options

    def explain_recommendation(self) -> str:
        try:
            options_text = json.dumps(
                self.recommended_options, ensure_ascii=False)
        except Exception:
            options_text = str(self.recommended_options)

        prompt = dedent(
            f"""
            Bạn là trợ lý giải thích lựa chọn gợi ý món ăn/uống.

            Mục tiêu: viết 1-2 câu giải thích *cụ thể* vì sao món được chọn và các recommended options phù hợp với nhu cầu trong truy vấn.
            - Viết cùng ngôn ngữ với truy vấn.
            - Chỉ nói về trường hợp hiện tại (không liệt kê quy tắc/không tự nhận xét về cách viết).
            - Không được bịa thêm dữ kiện y khoa/dinh dưỡng/calo/giá cả; nếu thiếu thông tin để kết luận mạnh, hãy dùng cách nói nhẹ nhàng (ví dụ: “thường phù hợp”, “có thể phù hợp”).
            - Không được lặp lại RECOMMENDED_OPTIONS dưới dạng JSON/dict/ngoặc {{}}/ngoặc []/ngoặc kép ("...") trong câu trả lời.
            - Nếu cần nhắc đến lựa chọn kèm theo, hãy nói chung chung kiểu “theo lựa chọn kèm theo của bạn”, không liệt kê key:value.
            - Tuyệt đối không viết các câu kiểu: “Không dùng từ ngữ…”, “Chỉ mô tả…”, “Không khuyến khích…”, “Use the same language…”.

            == USER_QUERY ==
            {self.parsing_prompt}

            == DISH ==
            {self.dish_name}

            == DISH_TYPE ==
            {self.dish_type}

            == RECOMMENDED_OPTIONS ==
            {options_text}

            Hãy trả lời đúng 1-2 câu.
            """
        ).strip()

        explanation = generate_text(
            task_type="rcm",
            prompt=prompt,
            max_new_tokens=128,
            temperature=0.1,
            do_sample=False,
        )
        if not isinstance(explanation, str):
            explanation = "" if explanation is None else str(explanation)
        cleaned = self._clean_explanation(explanation)
        if not cleaned or self._looks_like_policy_text(cleaned):
            return self._fallback_explanation(
                user_query=self.parsing_prompt,
                dish_name=self.dish_name,
                dish_type=self.dish_type,
                recommended_options=self.recommended_options,
            )
        return cleaned

    @staticmethod
    def _looks_like_policy_text(text: str) -> bool:
        s = (text or "").strip().lower()
        if not s:
            return True
        bad_phrases = (
            "không dùng từ ngữ",
            "chỉ mô tả",
            "không khuyến khích",
            "dấu câu",
            "đảm bảo",
            "use the same language",
            "only output",
        )
        return any(p in s for p in bad_phrases)

    @staticmethod
    def _fallback_explanation(
        user_query: str,
        dish_name: str,
        dish_type: str,
        recommended_options: object,
    ) -> str:
        # Deterministic, safe fallback (no new facts). Do not echo raw options.
        q = (user_query or "").strip()
        name = (dish_name or "").strip() or "món này"
        dtype = (dish_type or "").strip()
        tail = f" ({dtype})" if dtype else ""
        if recommended_options:
            return f"Với nhu cầu trong truy vấn, hệ thống gợi ý {name}{tail} và điều chỉnh lựa chọn kèm theo theo sở thích bạn đã chọn để phù hợp hơn với bối cảnh/khẩu vị bạn nêu."
        return f"Dựa trên truy vấn của bạn, hệ thống gợi ý {name}{tail} vì phù hợp với nhu cầu và bối cảnh bạn mô tả."

    @staticmethod
    def _clean_explanation(text: str) -> str:
        s = (text or "").strip()

        # Strip common wrappers from some backends.
        if "assistant" in s:
            s = s.split("assistant", 1)[-1].strip()
        s = re.sub(r"^```.*?\n", "", s, flags=re.DOTALL)
        s = re.sub(r"```$", "", s).strip()

        # Drop obvious prompt-leak / instruction lines.
        bad_markers = (
            "PARSING_PROMPT",
            "USER_QUERY",
            "RECOMMENDED OPTIONS",
            "DISH TYPE",
            "DISH ==",
            "Chỉ được dùng thông tin",
            "Viết cùng ngôn ngữ",
            "Chỉ xuất ra",
            "Use the same language",
            "Only output",
            "Do not",
            "Không dùng từ ngữ",
            "Chỉ mô tả",
            "Không khuyến khích",
            "dấu câu",
            "Đảm bảo",
        )
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        cleaned_lines = []
        for ln in lines:
            if any(m in ln for m in bad_markers):
                continue
            # Remove common "chain-of-thought" style preambles.
            if re.match(r"^(okay,|ok,|let's |i should\b|the user\b)", ln, flags=re.IGNORECASE):
                continue
            cleaned_lines.append(ln)
        lines = cleaned_lines
        s = " ".join(lines).strip()

        # Remove common formatting/policy prefixes that some models emit.
        # Example: "Đảm bảo ..." then real explanation.
        s = re.sub(r"^Đảm bảo[^.!?。！？]*[.!?。！？]\s*", "", s).strip()

        # Remove a leading label if present.
        s = re.sub(r"^(giải thích\s*:|explanation\s*:)",
                   "", s, flags=re.IGNORECASE).strip()

        # If the model echoed JSON/dict-like blobs, drop them.
        # Examples seen: ({"trứng":"không",...}) or {'a': 'b'} or "key":"value" chunks.
        s = re.sub(r"\(\s*\{.*?\}\s*\)", " ", s, flags=re.DOTALL).strip()
        s = re.sub(r"\{.*?\}", " ", s, flags=re.DOTALL).strip()
        s = re.sub(r"\(\s*\[.*?\]\s*\)", " ", s, flags=re.DOTALL).strip()
        s = re.sub(r"\[.*?\]", " ", s, flags=re.DOTALL).strip()
        s = re.sub(r"\(\s*['\"][^\)]*?:[^\)]*?\)\s*", " ", s).strip()
        s = re.sub(r"\s{2,}", " ", s).strip()

        # Keep it short: at most 2 sentences (roughly).
        parts = re.split(r"(?<=[.!?。！？])\s+", s)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 2:
            s = " ".join(parts[:2]).strip()
        return s
