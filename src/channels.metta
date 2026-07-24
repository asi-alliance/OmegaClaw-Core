;configured at runtime:
(= (commchannel) (empty))

;Connect all the channels:
(= (initChannels)
   (progn (log INFO "channels" "Initializing channels")
          (configure commchannel irc)
          (commChannelConfig (commchannel))))

(= (commChannelConfig $commchannel)
   (py-call (channels.commChannelConfig $commchannel (py-call (plugin.commandLineToDict (command-line))))))

(= (commChannelReceive)
   (py-call (channels.commChannelReceive)))

(= (commChannelSend $message)
   (py-call (channels.commChannelSend $message)))

;Receive the latest user message considering all communication channels:
(= (receive)
   (commChannelReceive))

;Send a message to all communication channels:
!(change-state! &lastsend "")
(= (send $msg)
   (if (!= $msg (get-state &lastsend))
       (progn (change-state! &lastsend $msg)
              (let $safemsg (string-replace $msg  "\n" "\\n")
                   (let $temp (cut) (commChannelSend $safemsg)))) _))
