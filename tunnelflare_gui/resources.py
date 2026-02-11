import sys
from pathlib import Path

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Base path is the root of the project in development
        # tunnelflare_gui/resources.py -> tunnelflare_gui -> root
        base_path = Path(__file__).parent.parent

    # The resources are actually in tunnelflare_gui/resources
    # But in the bundle we might flatten them or keep the structure.
    # Let's assume we keep the structure for simplicity: tunnelflare_gui/resources/...
    return base_path / "tunnelflare_gui" / "resources" / relative_path

# Root of the resources directory
RESOURCE_DIR = get_resource_path("")
