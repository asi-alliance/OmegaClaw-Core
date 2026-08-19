"""Every third-party module the plugin imports is declared in requirements.txt.

Two dependencies were shipped undeclared before this test existed (yaml/openai,
then requests), and the suites could not catch either: they stub the code paths
that reach them, so a clean install passed every test and failed at runtime.
This reads the imports out of the source instead, so a missing declaration fails
here rather than in front of a user.
"""
import ast
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_HERE)
_REQUIREMENTS = os.path.join(_PLUGIN_DIR, "requirements.txt")

# Import name -> distribution name, where they differ.
_DISTRIBUTION = {
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "telegramify_markdown": "telegramify-markdown",
}

# Imported on purpose without being declared. See requirements.txt for why.
_ALLOWED_UNDECLARED = {"chromadb"}

# Provided by core, not installable from here. Only what is actually imported:
# if the plugin starts using another of core's modules, the test says so.
# channels/config/plugin come from core's src/; auth and delivery_queue are
# shared channel infrastructure that lives in core's channels/ folder.
_CORE_MODULES = {"channels", "config", "plugin", "auth", "delivery_queue"}


def _plugin_modules():
    """The plugin's own modules, which are imported by bare name."""
    return {f[:-3] for f in os.listdir(_PLUGIN_DIR) if f.endswith(".py")}


def _imported_top_level_modules():
    """Every module imported anywhere in the plugin, including inside functions."""
    found = set()
    for filename in sorted(os.listdir(_PLUGIN_DIR)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(_PLUGIN_DIR, filename)
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                # A relative import is local, never a distribution.
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return found


def _declared_distributions():
    """Distribution names in requirements.txt, lowercased."""
    declared = set()
    with open(_REQUIREMENTS, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = re.split(r"[<>=!~\[;]", line)[0].strip()
            if name:
                declared.add(name.lower())
    return declared


def test_every_third_party_import_is_declared():
    declared = _declared_distributions()
    local = _plugin_modules() | _CORE_MODULES
    missing = []

    for module in sorted(_imported_top_level_modules()):
        if module in sys.stdlib_module_names or module in local:
            continue
        if module in _ALLOWED_UNDECLARED:
            continue
        distribution = _DISTRIBUTION.get(module, module).lower()
        if distribution not in declared:
            missing.append(f"{module} (expected '{distribution}' in requirements.txt)")

    assert not missing, "undeclared third-party imports: " + ", ".join(missing)


def test_allowed_undeclared_are_actually_imported():
    """Keep the exception list honest: drop entries that no longer apply."""
    imported = _imported_top_level_modules()
    stale = sorted(_ALLOWED_UNDECLARED - imported)
    assert not stale, f"no longer imported, remove from the exception list: {stale}"


if __name__ == "__main__":
    test_every_third_party_import_is_declared()
    test_allowed_undeclared_are_actually_imported()
    print("all requirements tests passed")
