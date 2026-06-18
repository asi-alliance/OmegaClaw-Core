;; Pay never done; trespass breach at t=20 within window [0,50].
(deadline (must pay) achieve 0 30 fine)
(deadline (forbidden trespass) maintain 0 50 penalty)
(given (during trespass 20 20))
