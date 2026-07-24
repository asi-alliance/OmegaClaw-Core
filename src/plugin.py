"""
This is OmegaClaw internal API which is built on the top of the plugins API.
Most of the functions here calls corresponding functions of the registered
plugins.
"""

import pathlib
import yaml
import importlib
import importlib.util
import sys
import logging

logger = logging.getLogger(__name__)

_LOADERS = ["python", "metta"]
_REPO = pathlib.Path(__file__).parent.parent.resolve()
_plugins = {}

def _error(func, text):
    error = f"{func}: {text}"
    logger.error(error)
    raise RuntimeError(error)

def listPlugins():
    """Loads the list of the plugins from ./config/plugins.yaml file and then
    returns list of triples (loader, name, location). YAML file
    contains the list of plugins each specified by three fields:
    - name - required, must be unique
    - loader - required, must be either "python" or "metta"
    - location - optional, path to the plugin module used by Python loader"""
    global _plugins, _REPO, _LOADERS

    config_path = _REPO.joinpath("./config/plugins.yaml")
    with open(config_path, "r") as f:
        yaml_content = yaml.safe_load(f)

    plugins = []
    for i, p in enumerate(yaml_content):
        name = p.get("name")
        if name is None:
            _error("listPlugins", f"name field is empty, file: {config_path}, index: {i}")
        if name in _plugins:
            _error("listPlugins", f"name '{name}' is not unique")

        loader = p.get("loader", "metta")
        if not loader in _LOADERS:
            _error("listPlugins", f"incorrect loader type '{loader}', only {_LOADERS} are supported")

        location = p.get("location")
        if location is not None:
            location = str(pathlib.Path(location.format(REPO=_REPO)).resolve())
        else:
            location = ""

        plugins.append([loader, name, location])

    return plugins

class PythonPlugin:
    """Class to wrap the reference to the Python module and keep it inside
    plugins registry"""

    def __init__(self, mod):
        self.mod = mod

def loadPythonPlugin(name, location):
    """Python plugin loader implementation. If location of the plugin is
    specified it imports "<location>/<name>.py" file. Imports <name> Python
    module otherwise. Calls "loadOmegaClawPlugin" function from the imported
    module. This is the point where plugin's code gets control and should
    register appropriate callbacks."""
    global _plugins, _REPO

    mod = None
    if not location:
        logger.info(f"_initPythonPlugin: loading {name} plugin from PYTHONPATH using Python module loader")
        mod = importlib.import_module(name)
    else:
        location = pathlib.Path(location.format(REPO=_REPO)).resolve()
        modpath = location.joinpath(f"{name}.py").resolve()
        logger.info(f"_initPythonPlugin: loading {name} plugin from {modpath} using Python module loader")
        # adding location into sys.path to be able loading plugins which
        # consist of multiple files
        sys.path.append(str(location))
        spec = importlib.util.spec_from_file_location(name, modpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    if mod is not None:
        _plugins[name] = PythonPlugin(mod)
    else:
        _error("_initPythonPlugin", f"Couldn't find Python module {name}")

    if not hasattr(mod, "loadOmegaClawPlugin"):
        _error("_initPythonPlugin", f"No loadOmegaClawPlugin() function is implemented by plugin {name}")
    plugin_loader = getattr(mod, "loadOmegaClawPlugin")
    plugin_loader()

def commandLineToDict(list):
    """Converts list of <key>=<value> pairs into Python dictionary. If
    parameter doesn't include "=" it is added as a boolean value
    <parameter>=True"""
    dict = {}
    for arg in list:
        kv = arg.split("=", 1)
        if len(kv) == 2:
            dict[kv[0]] = kv[1]
        else:
            dict[kv[0]] = True
    return dict
