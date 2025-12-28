from Backend.app.utils.model_utils import llmInitialize


class ExplainationService:
    def __init__(self, parsing_prompt, dish_name, recommended_options):
        self.model, self.tokenizer = llmInitialize.initialize_LLM(
            task_type="rcm")
        self.parsing_prompt = parsing_prompt
        self.dish_name = dish_name
        self.recommended_options = recommended_options

    def explain_recommendation(self) -> str:
        # if self.model is None or self.tokenizer is None:
        #     raise RuntimeError(
        #         "LLM (rcm) is not initialized. Check MODEL_NAME env for rcm.")

        # prompt = f"""
        # You are a nutrition advisor.
        # Use ONLY the information in PROMPT, DISH, and RECOMMENDED OPTIONS.
        # Do NOT invent nutrition facts, ingredients, calories, prices, or medical claims.
        # If the information is insufficient, say what is missing.

        # == PROMPT ==
        # {self.parsing_prompt}

        # == DISH ==
        # Dish name: {self.dish_name}

        # == RECOMMENDED OPTIONS ==
        # {self.recommended_options}

        # Write 3-5 concise sentences explaining why these options fit the user's needs.
        # """

        # inputs = self.tokenizer(
        #     prompt, return_tensors="pt").to(self.model.device)
        # output = self.model.generate(
        #     **inputs,
        #     max_new_tokens=256,
        #     temperature=0.7,
        #     do_sample=True
        # )
        # prompt_len = inputs["input_ids"].shape[-1]
        # new_tokens = output[0][prompt_len:]
        # explanation = self.tokenizer.decode(
        #     new_tokens, skip_special_tokens=True)
        # return explanation.strip()

        
        return f"Chọn {self.dish_name} với {self.recommended_options} vì phù hợp nhu cầu trong query."
