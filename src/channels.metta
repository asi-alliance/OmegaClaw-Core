;configured at runtime:
(= (isTelegram) (== (commchannel) telegram))
(= (IRC_channel) (empty))
(= (IRC_server) (empty))
(= (IRC_port) (empty))
(= (IRC_user) (empty))
(= (commchannel) (empty))
(= (MM_URL) (empty))
(= (MM_CHANNEL_ID) (empty))
(= (MM_BOT_TOKEN) (empty))
(= (BOT_TOKEN) (empty))
(= (CHAT_ID) (empty))

;Connect all the channels:
(= (initChannels)
   (progn (println! "Initializing channels")
          (configure commchannel telegram)
          (case (commchannel)
                ((irc      (progn (configure IRC_channel ##metta)
                                  (configure IRC_server "irc.quakenet.org")
                                  (configure IRC_port 6667)
                                  (configure IRC_user maxbotnick)
                                  (py-call (irc.start_irc (IRC_channel) (IRC_server) (IRC_port) (IRC_user)))))
                 (telegram  (progn (configure BOT_TOKEN "")
                                    (configure CHAT_ID "5116139198")
                                   (py-call (tg_channel.start_telegram (BOT_TOKEN) (CHAT_ID)))))
                 ($_ (progn (configure MM_URL "https://chat.singularitynet.io")
                            (configure MM_CHANNEL_ID "8fjrmabjx7gupy7e5kjznpt5qh")
                            (configure MM_BOT_TOKEN "acympttqpjyjfnm9j65gz7mzbw")
                            (py-call (mattermost.start_mattermost (MM_URL) (MM_CHANNEL_ID) (MM_BOT_TOKEN)))))))))

;Receive the latest user message considering all communication channels:
(= (receive)
   (case (commchannel)
         ((irc      (py-call (irc.getLastMessage)))
          (telegram  (py-call (tg_channel.getLastMessage)))
          ($_ (py-call (mattermost.getLastMessage))))))

;Send a message to all communication channels:
(= (send $msg)
   (let $safemsg (string-replace $msg  "\n" "\\n")
        (case (commchannel)
              ((irc      (let $temp (cut) (py-call (irc.send_message $safemsg))))
               (telegram  (let $temp (cut) (py-call (tg_channel.send_message $safemsg))))
               ($_ (let $temp (cut) (py-call (mattermost.send_message $safemsg))))))))

;Search the internet for some information:
(= (search $msg)
   (py-call (websearch.search $msg)))
