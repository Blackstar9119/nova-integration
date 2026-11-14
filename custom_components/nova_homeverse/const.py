"""Konstanten der Integration Nova Homeverse."""

DOMAIN = "nova_homeverse"
# Domain der alten Integration „Nova“. Beide dürfen nicht gleichzeitig laufen: dieselben Daten und Karten.
OLD_DOMAIN = "nova"
ISSUE_OLD_DOMAIN = "old_nova_installed"
# Präfix für Speicher (.storage/nova_homeverse.<name>) und WebSocket-Befehle (nova_homeverse/<modul>/<befehl>)
STORAGE_PREFIX = DOMAIN
# Vor der Umbenennung: Speicher .storage/nova.<name>, Bilder www/nova – werden beim Start einmalig übernommen
OLD_STORAGE_PREFIX = "nova"
OLD_IMAGE_DIR = "www/nova"
API_VERSION = 1
STORAGE_VERSION = 1
SAVE_DELAY = 2

# Module: Schlüssel = Name in der WebSocket-API (nova_homeverse/<modul>/…) und im Speicher (.storage/nova_homeverse.<modul>)
MODULES = ("theme", "notes", "shopping", "recipes")
CONF_MODULES = "modules"
# Eigene Speicher (.storage/nova_homeverse.<name>). Das Theme liegt in den Einstellungen (allgemein.theme).
STORES = ("settings", "notes", "shopping", "recipes")

# Bilder liegen in /config/www/nova_homeverse/<modul>/ und sind über /local/nova_homeverse/<modul>/<datei> erreichbar
IMAGE_DIR = "www/nova_homeverse"
IMAGE_URL = "/local/nova_homeverse/{module}/{name}"
IMAGE_MODULES = ("shopping", "recipes")
IMAGE_MAX_BYTES = 800_000

THEMES = ("blau", "hell", "midnight", "velvet")
BOOK_STYLES = ("old", "modern", "fantasy")
THEME_HELPER = "input_select.nova_theme"

# Statische Dateien (Karten, Panel, Schriften des Rezeptbuchs) unter /nova_homeverse/static
STATIC_URL = "/nova_homeverse/static"
# Nova Cards liefert die Integration selbst aus (static/nova-cards.js, gebaut mit „npm run integration“, nie von Hand ändern)
CARDS_FILE = "nova-cards.js"
CARDS_URL = f"{STATIC_URL}/{CARDS_FILE}"
# Nova-Panel in der Seitenleiste: Adresse /nova-homeverse, Element aus static/nova-panel.js
PANEL_URL = "nova-homeverse"
PANEL_ELEMENT = "nova-homeverse-panel"

UNITS = ["Stk", "g", "kg", "ml", "l", "Packung"]
RECIPE_UNITS = [*UNITS, "TL", "EL", "Prise", "Msp.", "Tasse", "Cup", "Becher", "cl", "Bund", "Dose", "Glas", "Zehe", "Scheibe", "Blatt", "Handvoll", ""]
HISTORY_MAX = 200
