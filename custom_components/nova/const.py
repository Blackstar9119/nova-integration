"""Konstanten der Nova-Integration."""

DOMAIN = "nova"
API_VERSION = 1
STORAGE_VERSION = 1
SAVE_DELAY = 2

# Module: Schlüssel = Name in der WebSocket-API (nova/<modul>/…) und im Speicher (.storage/nova.<modul>)
MODULES = ("theme", "notes", "shopping", "recipes")
CONF_MODULES = "modules"
# Eigene Speicher (.storage/nova.<name>). Das Theme liegt seit den Einstellungen in nova.settings (allgemein.theme).
STORES = ("settings", "notes", "shopping", "recipes")

# Bilder liegen in /config/www/nova/<modul>/ und sind über /local/nova/<modul>/<datei> erreichbar
IMAGE_DIR = "www/nova"
IMAGE_URL = "/local/nova/{module}/{name}"
IMAGE_MODULES = ("shopping", "recipes")
IMAGE_MAX_BYTES = 800_000

THEMES = ("blau", "hell", "midnight", "velvet")
BOOK_STYLES = ("old", "modern", "fantasy")
THEME_HELPER = "input_select.nova_theme"

UNITS = ["Stk", "g", "kg", "ml", "l", "Packung"]
RECIPE_UNITS = [*UNITS, "TL", "EL", "Prise", "Msp.", "Tasse", "Cup", "Becher", "cl", "Bund", "Dose", "Glas", "Zehe", "Scheibe", "Blatt", "Handvoll", ""]
HISTORY_MAX = 200
