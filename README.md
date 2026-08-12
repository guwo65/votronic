# votronic
HA-Integration für den Votronic Bluetooth Connector S-BC

In Bearbeitung —  funktionsfähig.

Da dein Connector noch nicht gekoppelt ist, muss in coordinator.py stehen:

PAIR_ON_NEXT_CONNECTION = True

1. Taste am SC-Connector drei Sekunden drücken.
2. Fünfmaliges LED-Signal abwarten – alle alten Kopplungen sind gelöscht.
3. Taste einmal kurz drücken.
4. Prüfen, ob beide LEDs abwechselnd blinken.
5. Innerhalb der dreiminütigen Frist die Votronic-Integration aktivieren.
6. Die Votronic-App am Smartphone oder Tablet dabei geschlossen lassen.
7. Wieder in coordinator.py: PAIR_ON_NEXT_CONNECTION = False 
  
Falls das Bonding irgendwann verloren geht, setzt du den Schalter vorübergehend auf True, öffnest mit kurzem Tastendruck den Pairingmodus und startest die Integration. Nach erfolgreichem Pairing muss er wieder auf False gesetzt werden.

guwo65/votronic/ (Hauptverzeichnis)
├── hacs.json
├── README.md
└── custom_components
    └── votronic
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── config_flow.py
        ├── coordinator.py
        ├── sensor.py
        ├── bluez_agent.py
