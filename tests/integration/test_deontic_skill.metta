; Tests for the agent-facing deontic skills.
!(import! &self (library OmegaClaw-Core src/skills_deontic))

; deontic-conclude returns the tagged conclusion set
!(test (is-member (pd (lit pos none none penguin ()))
                  (deontic-conclude (dl-path examples/deontic/penguin.metta))) True)

; deontic-conflicts surfaces an unresolved O p / O not-p dilemma, and none without one
!(test (size-atom (deontic-conflicts (dl-path examples/deontic/deontic_dilemma.metta))) 1)
!(test (size-atom (deontic-conflicts (dl-path examples/deontic/penguin.metta))) 0)

!(println! test-deontic-skill-done)
