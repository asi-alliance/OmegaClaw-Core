;; Telegram channel plugin.
;;
;; Registers the aiogram-based communication channel, the two media skills that
;; come with it, and the channel's own prompt section. Everything the plugin
;; adds is registered here at load time, so core needs no telegram-specific
;; code of its own.

;; No import! of the .py files is needed: the loader puts this folder on
;; sys.path, and py-call imports a module on first use. Keeping the plugin free
;; of (library OmegaClaw-Core ./plugins/...) paths is what lets it live outside
;; the core tree.
;;
;; The channel module is NOT called telegram.py. The plugin folder is appended
;; to sys.path rather than prepended, so a module named telegram would lose to
;; the python-telegram-bot package whenever that is installed.

; Ask the plugin's own module where its files are. Deriving the path from the
; repository root instead would tie the plugin to living inside the core tree.
(= (pluginTelegramPromptPath)
   (py-call (telegram_channel.prompt_path)))

(= (loadOmegaClawPlugin)
   (progn
     (log INFO "telegram-plugin" "Registering Telegram communication channel")
     (let $rc (py-call (telegram_channel.loadOmegaClawPlugin)) ())
     (add-skill describe-image
                "See/read an image the user attached. Call when a message shows [image] and you need its contents; optionally pass what to look for (example: describe-image what error is shown)"
                (query))
     (add-skill generate-image
                "Generate an image and send it to the user. Use when the user asks you to create, draw, generate, paint, or show a picture or image. Pass a vivid, detailed English description; the image is generated and sent for you (example: generate-image a red panda astronaut floating in space, studio lighting)"
                (description))
     (addTelegramPromptSection)
     ()))

;; The channel talks to the public, so it carries scope limits the default
;; prompt has no reason to include. Added as a prompt section rather than by
;; replacing the prompt file, so it composes with whichever provider prompt the
;; host is already using.
(= (addTelegramPromptSection)
   (if (exists-file (pluginTelegramPromptPath))
       (add-prompt-extension telegram-guardrails (read-file (pluginTelegramPromptPath)))
       (log WARN "telegram-plugin"
            (strings-concat ("No prompt section at " (pluginTelegramPromptPath) ", skipping")))))

(= (describe-image $query)
   (py-call (media_handler.describe_image $query)))

(= (generate-image $prompt)
   (py-call (media_handler.generate_and_send $prompt)))
