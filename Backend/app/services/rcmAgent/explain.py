import json
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
            You are a nutrition advisor.
            Use ONLY the information in PARSING_PROMPT, DISH, DISH_TYPE, and RECOMMENDED OPTIONS.
            Do NOT invent nutrition facts, ingredients, calories, prices, or medical claims.
            If the information is insufficient, say what is missing.

            Write in the SAME LANGUAGE as PARSING_PROMPT.

            == PARSING_PROMPT ==
            {self.parsing_prompt}

            == DISH ==
            Dish name: {self.dish_name}

            == DISH TYPE ==
            Dish type: {self.dish_type}

            == RECOMMENDED OPTIONS ==
            {options_text}

            Write 3-5 concise sentences explaining why these options fit the user's needs.
            """
        ).strip()

        explanation = generate_text(
            task_type="rcm",
            prompt=prompt,
            max_new_tokens=256,
            temperature=0.7,
            do_sample=True,
        )
        if not isinstance(explanation, str):
            explanation = "" if explanation is None else str(explanation)
        return explanation.strip()
