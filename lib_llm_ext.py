import os, openai

def _init_openai_client(var_name, base_url):
    if var_name in os.environ:
        return openai.OpenAI(api_key=os.environ[var_name], base_url=base_url)
    else:
        return None

ASI_CLIENT = _init_openai_client(
    var_name="ASI_API_KEY",
    base_url="https://inference.asicloud.cudos.org/v1")
)

ANTHROPIC_CLIENT = _init_openai_client(
    var_name="ANTHROPIC_API_KEY",
    base_url="https://api.anthropic.com/v1/"
)

def _clean(text):
    return text.replace("_quote_", '"').replace("_apostrophe_", "'")

def _chat(client, model, content, max_tokens=6000):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=max_tokens
    )
    return _clean(resp.choices[0].message.content)

def useMiniMax(content):
    return _chat(
        client=ASI_CLIENT,
        model="minimax/minimax-m2.5",
        content=content
    )

def useClaude(content):
    return _chat(
        client=ANTHROPIC_CLIENT,
        model="claude-opus-4-6",
        content=content
    )
