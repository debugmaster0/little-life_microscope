import base64
import json
import os
from typing import Any, Dict
from secrets_store import get_openai_api_key
from openai import OpenAI

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY") or get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "OpenAI API key not set. Set OPENAI_API_KEY (dev) or add a key in the app."
            )
        _client = OpenAI(api_key=api_key)
    return _client

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def _b64_data_url(image_path: str) -> str:
    # Basic MIME detection
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _context_hint(sample_type: str) -> str:
    st = (sample_type or "Other").strip().lower()
    hints = {
        "pond": (
            "Assume a pond/wet mount sample. Consider common freshwater microorganisms "
            "(protozoa, rotifers, algae/diatoms, nematodes, small crustaceans, etc.)."
        ),
        "soil": (
            "Assume a soil sample. Consider soil organisms and structures "
            "(mites, nematodes, fungal hyphae/spores, pollen, plant fibers), and mineral grains."
        ),
        "tissue": (
            "Assume a tissue/biological smear. Consider common cell types and structures "
            "(epithelial cells, red/white blood cells if applicable, parasites/eggs, bacteria patterns if visible)."
        ),
        "crystal": (
            "Assume a crystal/mineral sample. Consider crystal habit, cleavage, inclusions, and "
            "common salts/minerals that appear under a microscope."
        ),
        "other": (
            "No specific sample context; identify the most likely subject and clearly note uncertainty."
        ),
    }
    return hints.get(st, hints["other"])


def _strip_code_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        # remove first fence line
        t = t.split("\n", 1)[1] if "\n" in t else ""
        # remove trailing fence
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        t = t.strip()
        if t.lower().startswith("json"):
            t = t[4:].lstrip()
    return t


def identify_image(image_path: str, sample_type: str = "Other") -> Dict[str, Any]:
    client = get_client()

    data_url = _b64_data_url(image_path)
    context = _context_hint(sample_type)

    prompt = (
        "You are helping identify microorganisms from microscope photos.\n"
        f"Context: {context}\n\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        "best_guess_name (string), confidence (integer 0-100), "
        "description (string), features_used (string).\n"
        "Be cautious: if unsure, lower confidence.\n"
    )

    resp = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    )

    text = _strip_code_fence(getattr(resp, "output_text", "") or "")

    try:
        result = json.loads(text)
    except Exception:
        raise ValueError(f"Model did not return JSON. Got:\n{text}")

    if not isinstance(result, dict):
        raise ValueError(f"Model returned non-dict JSON. Got:\n{text}")

    result.setdefault("best_guess_name", "Unknown")
    result.setdefault("confidence", 0)
    result.setdefault("description", "")
    result.setdefault("features_used", "")

    try:
        result["confidence"] = int(result["confidence"])
    except Exception:
        result["confidence"] = 0

    result["confidence"] = max(0, min(100, result["confidence"]))
    return result
