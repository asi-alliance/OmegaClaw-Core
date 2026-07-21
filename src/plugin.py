"""
This is OmegaClaw internal API which is built on the top of the plugins API.
Most of the functions here calls corresponding functions of the registered
plugins.
"""

import pathlib
import yaml
import importlib
import importlib.util
import pluginapi
import sys
import logging

logger = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).parent.parent.resolve()
_plugins = {}
_commchannel: pluginapi.CommChannel = None
_llmprovider: pluginapi.LLMProvider = None

def _error(func, text):
    error = f"{func}: {text}"
    logger.error(error)
    raise RuntimeError(error)

def initPlugins():
    """Loads the list of the plugins from ./config/plugins.yaml file and then
    loads each plugin from the list using the specified loader. YAML file
    contains the list of plugins each specified by three fields:
    - name - required, must be unique
    - loader - required, must be either "python" or "metta"
    - location - optional, path to the plugin module used by Python loader"""
    global _plugins, _REPO

    plugins_path = _REPO.joinpath("./config/plugins.yaml")
    with open(plugins_path, "r") as f:
        plugins = yaml.safe_load(f)

    for i, p in enumerate(plugins):

        name = p.get("name")
        if name is None:
            _error("initPlugins", f"name field is empty, file: {plugins_path}, index: {i}")
        if name in _plugins:
            _error("initPlugins", f"name '{name}' is not unique")

        loader = p.get("loader", "metta")
        if loader == "python":
            _initPythonPlugin(p)
        elif loader == "metta":
            _initMettaPlugin(p)
        else:
            _error("initPlugins", f"loader '{loader}' is not implemented")

class PythonPlugin:
    """Class to wrap the reference to the Python module and keep it inside
    plugins registry"""

    def __init__(self, mod):
        self.mod = mod

def _initPythonPlugin(plugin):
    """Python plugin loader implementation. If location of the plugin is
    specified it imports "<location>/<name>.py" file. Imports <name> Python
    module otherwise. Calls "loadOmegaClawPlugin" function from the imported
    module. This is the point where plugin's code gets control and should
    register appropriate callbacks."""
    global _plugins, _REPO

    name = plugin.get("name")
    location = plugin.get("location")
    mod = None
    if location is None:
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

def _initMettaPlugin(plugin):
    raise NotImplementedError()

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

def commChannelConfig(commchannel, config):
    """Select and configure one of the communication channels registered by
    plugins"""
    global _commchannel
    _commchannel = pluginapi._commChannelRegistry.get(commchannel, None)
    if _commchannel is None:
        _error("commChannelConfig", f"Communication channel plugin {commchannel} is not registered")
    _commchannel.config(config)

def commChannelReceive():
    """Receive message from selected communication channel"""
    global _commchannel
    return _commchannel.receive()

def commChannelSend(message):
    """Send message via selected communication channel"""
    global _commchannel
    _commchannel.send(message)

def llmProviderConfig(provider, config):
    """Select and configure one of the LLM providers registered by plugins"""
    global _llmprovider
    _llmprovider = pluginapi._llmProviderRegistry.get(provider, None)
    if _llmprovider is None:
        _error("llmProviderConfig", f"LLM provider plugin {provider} is not registered")
    _llmprovider.config(config)

def llmProviderChat(prompt, max_tokens, reasoning_mode):
    """Chat via selected LLM provider"""
    global _llmprovider
    import time
    t0 = time.monotonic()
    response = _llmprovider.chat(prompt, max_tokens, reasoning_mode)
    # Reasoning trace (Issue #7): emit an llm_call trace under the current iteration's trace_id.
    # Best-effort — a trace failure never breaks the chat path.
    try:
        try:
            import tracing
        except ImportError:  # pragma: no cover - package-style import path
            from src import tracing
        provider_name = getattr(_llmprovider, "_name", "")
        model = getattr(getattr(_llmprovider, "delegate", None), "_model_name", "")
        tracing.trace_llm(provider_name, model, prompt, response,
                          latency_ms=int((time.monotonic() - t0) * 1000))
    except Exception:
        pass
    return response
