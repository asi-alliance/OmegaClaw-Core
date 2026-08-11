; Initialize configuration: load configuration file and drop configuration
; cache.
(= (initConfig)
   (progn
     (py-call (config.init_config (command-line)))
     ()))

; Get the value of the $key (use $default if $key is not found) and add ($key)
; function to the atomspace to allow using MeTTa call for getting the
; parameter's value.
(= (configure $key $default)
   (let $value (configGetByKey $key $default)
     (add-atom &self (= ($key) $value))))

; Configure a value that must be a positive integer.
(= (configurePositiveInt $key $default)
   (let $value (py-call (config.config_get_positive_int $key $default))
     (add-atom &self (= ($key) $value))))

; Get configuration parameter from the list of sources: (1) command line
; parameters, (2) environment variable with OMEGACLAW_$key name, (3)
; configuration file, (4) use $default value.
(= (configGetByKey $key $default)
   (py-call (config.config_get_by_key $key $default)))
