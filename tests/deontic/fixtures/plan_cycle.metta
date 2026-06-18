;; Deadlock: ready-a waits on ready-b, ready-b waits on ready-a (circular).
(given start)
(normally rA ready-b ready-a)
(normally rB ready-a ready-b)
(normally r0 start ready-c)
