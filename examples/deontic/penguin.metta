; Classic Tweety/Penguin example
; Penguins are birds that don't fly

(given bird)
(given penguin)

(normally r1 bird flies)
(normally r2 penguin (not flies))

; Penguins are more specific than birds
(prefer r2 r1)
