"""Konstanten der Nova-Integration."""

DOMAIN = "nova"
API_VERSION = 1
STORAGE_VERSION = 1
SAVE_DELAY = 2

# Module: Schlüssel = Name in der WebSocket-API (nova/<modul>/…) und im Speicher (.storage/nova.<modul>)
MODULES = ("theme", "notes", "shopping", "recipes")
CONF_MODULES = "modules"

# Bilder liegen in /config/www/nova/<modul>/ und sind über /local/nova/<modul>/<datei> erreichbar
IMAGE_DIR = "www/nova"
IMAGE_URL = "/local/nova/{module}/{name}"
IMAGE_MODULES = ("shopping", "recipes")
IMAGE_MAX_BYTES = 800_000

THEMES = ("blau", "hell", "midnight", "velvet")
THEME_HELPER = "input_select.nova_theme"

UNITS = ["Stk", "g", "kg", "ml", "l", "Packung"]
RECIPE_UNITS = [*UNITS, "TL", "EL", "Prise", "Bund", "Dose", "Zehe", "Scheibe", ""]
HISTORY_MAX = 200
