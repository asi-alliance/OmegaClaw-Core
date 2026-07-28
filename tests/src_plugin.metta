!(import! &self ./tests/lib/utils)
!(import! &self ./src/utils)
!(import! &self ../src/logger.py)
!(import! &self ./src/log)
!(import! &self ./src/plugin)

!(initLogger)

!(test (= (cons Error (cons $_ $error)) (Error A B)) True)
!(test (= (cons Error (cons $_ $error)) True) False)

!(test (loadPlugin (metta "test_plugin" "./tests/res")) ())

!(test
   (progn
     (loadPlugin (metta "test_plugin" "./tests/res"))
     (get-state &test_plugin_loaded))
   True)

!(test (loadPlugin (metta "test_plugin_error" "./tests/res"))
   (Error (_loadOmegaClawPlugin) "Plugin internal error"))
