import os

def get_openai_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. "
            "Set it in your shell or launcher script."
        )
    return key
