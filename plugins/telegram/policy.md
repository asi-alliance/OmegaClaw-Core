# START

This bot reads messages in the chats it is added to and replies only when
directly tagged or replied to. It can read images, PDFs and voice notes you
attach, and can generate images. Do not share passwords, tokens, private keys or
sensitive personal data.

**About this bot**

- It reads messages in this chat, and replies only when tagged or replied to.
- Message text is checked by an external moderation service before the bot acts
  on it and before it replies.
- Attached images are re-encoded to strip metadata, then sent to an external
  vision model when the bot needs to read them.
- Attached PDFs have their text extracted on the machine running the bot; that
  text is then included in what the bot's language model sees.
- Attached voice and audio notes are sent to an external transcription service.
- It can generate an image from a description and send it back, using an external
  image service.
- It may use limited web lookups to answer questions.
- It keeps limited durable memory for chat norms, stated preferences and useful
  learned patterns. It does not build hidden dossiers or profiles of people.
- It does not act outside this chat except for the lookups and services above,
  and any files it reads or writes are confined to a restricted set of paths.

**Use notes**

- Tag the bot directly if you want a reply.
- Some requests are refused for safety or privacy reasons.
- Admins can pause the bot in a chat, or clear its long-term memory.

# ABOUT

I am an OmegaClaw agent reachable over Telegram.

What I can do:

- read this chat's messages and reply when tagged or replied to
- read images you attach, using an external vision model
- read text out of PDFs you attach
- transcribe voice and audio notes you send, using an external service
- generate an image from a description and send it to you
- perform limited web lookups

What I will not do:

- speak for the ASI Alliance, SingularityNET or any affiliate
- give financial, investment or trading advice, or predict prices or outcomes
- endorse projects, tokens, people or counterparties
- repeat or act on rumours, allegations or legal matters
- store sensitive personal data

Privacy and memory:

- Your message text, and anything you attach, is sent to the external services
  listed above so that I can process it.
- I keep limited memory for chat norms, stated preferences and useful learned
  patterns. I do not build durable profiles of people.
- Please do not send secrets or sensitive personal data.

# PRIVACY

This bot reads messages in the chats it joins and replies only when tagged or
replied to.

What leaves the machine running the bot:

- Message text, inbound and outbound, goes to an external moderation service.
- Message text goes to the language model that generates replies.
- Images you attach are stripped of metadata and sent to an external vision model
  when the bot reads them.
- Voice and audio notes are sent to an external transcription service.
- Image-generation prompts are sent to an external image service.

PDF text is extracted locally, but the extracted text then reaches the language
model along with your message.

Limited memory is retained for chat norms, stated preferences and useful learned
patterns. Sensitive personal data and durable profiling of people are out of
scope. Ask an admin if you want the bot's memory reviewed or cleared.
