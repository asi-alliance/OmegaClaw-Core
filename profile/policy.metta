!(import! &self (library OmegaClaw-Core ./profile/policy.py))

(= (securityPolicyPath) (empty))

(= (applySecurityPolicy)
   (progn (log INFO "policy" "Configuring security policy")
          (configure securityPolicyPath "./repos/OmegaClaw-Core/profile/policy.yaml")
          (py-call (policy.apply_security_policy (securityPolicyPath)))
          True))
