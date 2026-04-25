import os, openai

_PROXY_ROUTES = {
    "https://api.anthropic.com/v1/":           "anthropic",
    "https://inference.asicloud.cudos.org/v1": "asi",
    "https://api.openai.com/v1":               "openai",
}

def _init_openai_client(var_name, base_url):
    proxy_url = os.environ.get("LLM_PROXY_URL")
    if proxy_url:
        prefix = _PROXY_ROUTES.get(base_url)
        if prefix is None:
            return None
        return openai.OpenAI(
            api_key="proxy",
            base_url=f"{proxy_url.rstrip('/')}/{prefix}/",
        )
    key = os.environ.pop(var_name, None)
    if key:
        return openai.OpenAI(api_key=key, base_url=base_url)
    return None

ASI_CLIENT = _init_openai_client(
    var_name="ASI_API_KEY",
    base_url="https://inference.asicloud.cudos.org/v1"
)

ANTHROPIC_CLIENT = _init_openai_client(
    var_name="ANTHROPIC_API_KEY",
    base_url="https://api.anthropic.com/v1/"
)

ASIONE_CLIENT = _init_openai_client(
    var_name="ASIONE_API_KEY",
    base_url="https://api.asi1.ai/v1"
)

def _clean(text):
    return text.replace("_quote_", '"').replace("_apostrophe_", "'")

def _chat(client, model, content, max_tokens=6000, **kwargs):
    content = content.replace(":-:-:-:", " ")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
            extra_body={
                "enable_thinking": True,
                "thinking_budget": 6000 
            },
            **kwargs
        )
        return _clean(resp.choices[0].message.content)
    except Exception as e:
        print(f"[lib_llm_ext._chat] Exception while communicating with LLM: {e}")
        return ""

def useMiniMax(content):
    return _chat(
        client=ASI_CLIENT,
        model="minimax/minimax-m2.7", #"asi1-mini"
        content=content
    )

def useClaude(content):
    return _chat(
        client=ANTHROPIC_CLIENT,
        model="claude-opus-4-6",
        content=content
    )

def _chatAsiOne(client, model, content, max_tokens=6000, **kwargs):
    spl = content.split(":-:-:-:")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": spl[0]},
                      {"role": "user", "content": spl[1]}],
            max_tokens=max_tokens,
            extra_body={
                "enable_thinking": True,
                "thinking_budget": 6000 
            },
            **kwargs
        )
        return _clean(resp.choices[0].message.content)
    except Exception as e:
        print(f"[lib_llm_ext._chat] Exception while communicating with LLM: {e}")
        return ""

def useAsi1(content):
    resp = _chatAsiOne(
        client=ASIONE_CLIENT,
        model="asi1-ultra", # "asi1-ultra"
        content=content
    )
    resp = resp.replace("</arg_value>", " ").replace("</tool_call>", " ").replace("<arg_value>", " ").replace("<tool_call>", " ")
    return resp

_embedding_model = None

def initLocalEmbedding():
    model_name="intfloat/e5-large-v2"
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model

def useLocalEmbedding(atom):
    global _embedding_model
    if _embedding_model is None:
        raise RuntimeError("Call initLocalEmbedding() first.")
    return _embedding_model.encode(
        atom,
        normalize_embeddings=True
    ).tolist()
