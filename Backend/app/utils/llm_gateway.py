import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from Backend.app.utils.model_utils import llmInitialize


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    obj = json.loads(body)
    return obj if isinstance(obj, dict) else {}


def generate_text(
    *,
    task_type: str,
    prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    max_new_tokens: int = 256,
    temperature: float = 0.0,
    do_sample: bool = False,
    allow_remote: bool = True,
) -> str:
    """
    Generates text using the specified LLM model.
    Args:
        task_type (str): The type of task for which the model is being used.
        prompt (Optional[str]): The prompt string to generate text from.
        messages (Optional[List[Dict[str, str]]]): A list of messages for chat-based models.
        max_new_tokens (int): The maximum number of new tokens to generate.
        temperature (float): The sampling temperature.
        do_sample (bool): Whether to use sampling or greedy decoding.
    Returns:
        str: The generated text.
    """

    modal_url = (os.getenv("MODAL_LLM_URL") or "").strip()
    if allow_remote and modal_url:
        payload = {
            "task_type": task_type,
            "prompt": prompt,
            "messages": messages,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "do_sample": do_sample,
        }
        try:
            obj = _post_json(modal_url, payload, timeout=180)
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Failed to call MODAL_LLM_URL={modal_url}. "
                f"Make sure it ends with '/generate' and is reachable. Underlying error: {exc}"
            ) from exc
        text = obj.get("text")
        if not isinstance(text, str):
            raise RuntimeError(f"Modal response invalid: {obj}")
        return text.strip()

    model, tokenizer = llmInitialize.initialize_LLM(task_type=task_type)
    if model is None or tokenizer is None:
        raise RuntimeError(
            f"LLM ({task_type}) is not initialized. Check MODEL_NAME env.")

    if messages is not None:
        if hasattr(tokenizer, "apply_chat_template"):
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
        else:
            prompt = "\n".join(
                [f"{m.get('role','')}: {m.get('content','')}" for m in messages])

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt/messages must be provided")

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=do_sample,
    )

    prompt_len = inputs["input_ids"].shape[-1]
    new_tokens = output[0][prompt_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
