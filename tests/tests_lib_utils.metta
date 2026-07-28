!(import! &self ./tests/lib/utils)

!(test (expression-count-item (a b c b d) b) 2)

!(test (contains-text "abcd" "bc") True)
!(test (contains-text "abcd" "de") False)
