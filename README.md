# votronic
HA-Integration für den Votronic Bluetooth Connector S-BC

In Bearbeitung —  funktionsfähig - Sensorwertzuordnungen überprüft, Bedeutung des Solarstaus unbekannt
Nur read, Der Reset-button setzt nur die HA-Werte auf 0, im Solar- und Batteriecomputer bleiben sie bestehen.

Download in HACS: guwo65/votronic

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
				├── button.py
        ├── bluez_agent.py
        ├── INSTALLATION.txt

## Haftungsausschluss

Dieses Projekt ist ein unabhängiges Community-Projekt.

Es steht in keiner Verbindung zu Votronic Elektronik-Systeme GmbH oder zu Herstellern der verwendeten Steuerelektronik und wird von diesen weder unterstützt noch bestätigt.

Die Nutzung erfolgt auf eigene Verantwortung.

Insbesondere bei elektrischen Verbrauchern sollten Schaltvorgänge zunächst unter Aufsicht an der eigenen Installation geprüft werden.

## Lizenz

Dieses Projekt steht unter der **MIT License**. Siehe [`LICENSE`](LICENSE).
