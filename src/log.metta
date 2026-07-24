!(import_prolog_function swrite)

(= (logConfigPath) (empty))

(= (initLogger)
   (progn
     (configure logConfigPath "")
     (py-call (logger.setup_logging (logConfigPath)))))

(= (log $type $module $msg)
   (let $str (swrite $msg)
     (case $type 
        ((INFO (py-call (logger.log_info $str $module)))
        (DEBUG (py-call (logger.log_debug $str $module)))
        (WARNING (py-call (logger.log_warning $str $module)))
        (ERROR (py-call (logger.log_error $str $module)))
        ($else ERROR-LOGGER-TYPE-UNIDENTIFIED)))))
