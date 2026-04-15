import os, openai

ASI_CLIENT = openai.OpenAI(
    api_key=os.environ["ASI_API_KEY"],
    base_url="https://inference.asicloud.cudos.org/v1"
)

ANTHROPIC_CLIENT = openai.OpenAI(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url="https://api.anthropic.com/v1/"
)

def _clean(text):
    return text.replace("_quote_", '"').replace("_apostrophe_", "'")

def _chat(client, model, content, max_tokens=6000):
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=max_tokens,
        extra_body={
            "enable_thinking": True,
            "thinking_budget": 6000
        }
    )
    return _clean(resp.choices[0].message.content)

def useMiniMax(content):
    return _chat(
        client=ASI_CLIENT,
        model="minimax/minimax-m2.7", #"minimax/minimax-m2.7", #"asi1-mini",
        content=content
    )

def useClaude(content):
    return _chat(
        client=ANTHROPIC_CLIENT,
        model="claude-opus-4-6",
        content=content
    )

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
