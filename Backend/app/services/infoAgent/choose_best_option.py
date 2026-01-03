import re
import json
from Backend.app.utils.llm_gateway import generate_text


class ChooseBestOptionService:
    def __init__(self, user_fields, dish_name, dish_type, base_options, canonical_description, health_profile, context_suitability):
        self.user_fields = user_fields
        self.dish_name = dish_name
        self.dish_type = dish_type
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

        option_schema = self._parse_option_schema(self.base_options)

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
        {{
          "recommended_options": {{
            "ice": "less",
            "sugar": "none"
          }}
        }}
        """
        decoded = generate_text(
            task_type="parsing",
            prompt=prompt,
            max_new_tokens=256,
            temperature=0.0,
            do_sample=False,
        )

        result = self._extract_recommended_options(decoded, option_schema)
        if result is None:
            # Hard fallback: still pick something deterministic so pipeline doesn't skip everything.
            return {"recommended_options": self._fallback_options(option_schema)}
        return {"recommended_options": result}

    @staticmethod
    def _parse_option_schema(base_options) -> dict:
        if isinstance(base_options, dict):
            return base_options
        if not isinstance(base_options, str):
            return {}
        s = base_options.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _clean_model_text(decoded: str) -> str:
        if not isinstance(decoded, str):
            return ""
        s = decoded.strip()
        # Some chat backends may include an 'assistant' prefix.
        if "assistant" in s:
            s = s.split("assistant", 1)[-1].strip()
        # Strip fenced code blocks.
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
        return s.strip()

    @classmethod
    def _extract_recommended_options(cls, decoded: str, option_schema: dict) -> dict | None:
        """Return a validated recommended_options dict or None."""
        text = cls._clean_model_text(decoded)
        if not text:
            return None

        # Try all JSON objects in the output; pick the one that contains recommended_options.
        candidates = re.findall(r"\{[\s\S]*\}", text)
        for chunk in reversed(candidates):
            try:
                obj = json.loads(chunk)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue

            rec = None
            if "recommended_options" in obj and isinstance(obj.get("recommended_options"), dict):
                rec = obj.get("recommended_options")
            else:
                # Some models may return the options dict directly.
                if all(isinstance(k, str) for k in obj.keys()) and all(
                    isinstance(v, str) for v in obj.values()
                ):
                    rec = obj

            if not isinstance(rec, dict):
                continue

            validated = cls._validate_against_schema(rec, option_schema)
            if validated:
                return validated

        return None

    @staticmethod
    def _validate_against_schema(rec: dict, option_schema: dict) -> dict:
        """Keep only keys in schema and values among allowed options."""
        if not isinstance(option_schema, dict) or not option_schema:
            # If schema missing, accept as-is if it looks like key->str.
            if all(isinstance(k, str) for k in rec.keys()) and all(isinstance(v, str) for v in rec.values()):
                return rec
            return {}

        out = {}
        for key, value in rec.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            allowed = option_schema.get(key)
            if isinstance(allowed, list) and value in allowed:
                out[key] = value
        return out

    @staticmethod
    def _fallback_options(option_schema: dict) -> dict:
        """Deterministic fallback: pick a 'healthier' looking default if present."""
        if not isinstance(option_schema, dict):
            return {}

        out = {}
        for key, allowed in option_schema.items():
            if not isinstance(key, str) or not isinstance(allowed, list) or not allowed:
                continue

            # Prefer common VN 'less/no' style if present.
            for preferred in ("không", "ít", "less", "none"):
                if preferred in allowed:
                    out[key] = preferred
                    break
            else:
                out[key] = allowed[0]

        return out
