; Testing utility functions

; Count how many times $expected item is contained in the $list list
(= (expression-count-item $list $expected)
   (let $agg (|-> ($res $item) (if (== $item $expected) (+ $res 1) $res))
     (foldl-atom $list 0 $agg)))

; Check whether $part string is contained inside $text string
(= (contains-text $full $part)
   (py-call (.__contains__ $full $part)))
