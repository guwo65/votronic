# Changelog

## v0.3.1 (2026-08-07)

- Fix: Added __init__.py to the integration package to provide Home Assistant the required setup functions (async_setup, async_setup_entry, async_unload_entry). This resolves the error "No setup or config entry setup function defined" when loading the custom integration.

- Ensure manifest.json is present and contains the correct domain and version.

