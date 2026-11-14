"""Konstanten der Integration Nova Homeverse."""

DOMAIN = "nova_homeverse"
# Domain der alten Integration „Nova“. Beide dürfen nicht gleichzeitig laufen: dieselben WebSocket-Befehle und Pfade.
OLD_DOMAIN = "nova"
ISSUE_OLD_DOMAIN = "old_nova_installed"
# Bewusst unverändert geblieben (Kompatibilität, Daten ohne Migration): Speicher .storage/nova.<name>,
# WebSocket-Befehle nova/…, Pfad /nova/static, Panel-Adresse /nova, Bildordner www/nova, input_select.nova_theme.
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

# Nova Cards liefert die Integration selbst aus (static/nova-cards.js, gebaut in nova-cards mit „npm run integration“)
CARDS_FILE = "nova-cards.js"
CARDS_URL = "/nova/static/nova-cards.js"

UNITS = ["Stk", "g", "kg", "ml", "l", "Packung"]
RECIPE_UNITS = [*UNITS, "TL", "EL", "Prise", "Msp.", "Tasse", "Cup", "Becher", "cl", "Bund", "Dose", "Glas", "Zehe", "Scheibe", "Blatt", "Handvoll", ""]
HISTORY_MAX = 200
