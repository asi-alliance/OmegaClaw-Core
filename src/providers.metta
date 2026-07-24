(= (llmProviderConfig $provider)
   (py-call (providers.llmProviderConfig $provider (py-call (plugin.commandLineToDict (command-line))))))

(= (llmProviderChat $prompt $max_tokens $reasoning_mode)
   (py-call (providers.llmProviderChat $prompt $max_tokens $reasoning_mode)))

