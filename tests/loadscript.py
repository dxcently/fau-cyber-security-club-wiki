"""Load a hyphenated script under scripts/ as an importable module.

The sync scripts live outside any package (hyphens in the filename rule out
a normal `import`) and guard their network/git side effects behind
`if __name__ == "__main__":`, so importing them here only defines their
functions — it never touches Discord, RSS feeds, or git.
"""
import importlib.util
import pathlib

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"

def load(name):
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
