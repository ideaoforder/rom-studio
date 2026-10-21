"""Shared paths for the dev scripts. Set SMB_ROM to your Super Mario Bros. (World) .nes (never commit it)."""
import os, sys
DEV = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(DEV)
ROM_PATH = os.environ.get("SMB_ROM") or sys.exit("Set SMB_ROM=/path/to/Super Mario Bros. (World).nes")
JSYAML = os.path.join(DEV, "node_modules/js-yaml/dist/js-yaml.min.js")
def bench_body():
    """index.html minus its head wrapper: the tests re-wrap it in a minimal page."""
    s = open(os.path.join(REPO, "index.html")).read()
    return s[s.index("<body>") + 6 : s.rindex("</body>")]
