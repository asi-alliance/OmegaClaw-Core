(= (llmProviderStart $provider)
   (py-call (providers.llmProviderStart $provider)))

(= (llmProviderChat $prompt $max_tokens $reasoning_mode)
   (py-call (providers.llmProviderChat $prompt $max_tokens $reasoning_mode)))

