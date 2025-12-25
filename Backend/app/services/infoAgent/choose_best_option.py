import re
import json
from Backend.app.utils.model_utils import llmInitialize


class ChooseBestOptionService:
    def __init__(self, user_fields, dish_name, base_options, canonical_description, health_profile, context_suitability):
        self.model, self.tokenizer = llmInitialize.initialize_LLM()

        self.user_fields = user_fields
        self.dish_name = dish_name
        self.base_options = base_options
        self.canonical_description = canonical_description
        self.health_profile = health_profile
        self.context_suitability = context_suitability

    def choose_best_option(self) -> dict:
        """
        Chooses the best option for a dish based on user fields using the LLM.
        Returns:
            dict: A dictionary with recommended options.
        """

        prompt = f"""
        You are a nutrition expert.
        Choose the most appropriate OPTION for the dish based on user preferences and health.

        == USER INFORMATION ==
        Health status: {self.user_fields.get("health_status")}
        Taste preference: {self.user_fields.get("taste")}
        Context: {self.user_fields.get("context")}

        == DISH ==
        Dish name: {self.dish_name}
        Description: {self.canonical_description}
        Health profile suitability: {self.health_profile}
        Context suitability: {self.context_suitability}

        == AVAILABLE OPTIONS ==
        {self.base_options}

        Return only valid JSON, do not explain or add text outside the JSON.
        If no perfect option exists, choose the closest or most common value for each factor.
        NOTE: ONLY USE OPTIONS FROM {self.base_options}, DO NOT INVENT NEW ONES.

        Example:
        "recommended_options": {{
            "ice": "less",
            "sugar": "none"
        }}
        """
        inputs = self.tokenizer(
            prompt, return_tensors="pt").to(self.model.device)
        output = self.model.generate(max_new_tokens=256, **inputs)
        decoded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        matches = re.findall(r"\{[\s\S]*?\}", decoded)
        if matches:
            try:
                return json.loads(matches[-1])
            except:
                return {"recommended_options": {}}
        else:
            return {"recommended_options": {}}
