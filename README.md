# Color Memory

Ein interaktives Farbgedächtnis-Spiel, entwickelt als HCI-Projekt an der Frankfurt University of Applied Sciences. Die App setzt auf [Flet](https://flet.dev) und kombiniert eine responsive Benutzeroberfläche mit Audio-Feedback, adaptivem Schwierigkeitsgrad und detaillierter Auswertung.

## Highlights

- Moderne Cross-Plattform-Oberfläche auf Basis von Flet (Material Design Komponenten)
- Adaptiver Spielablauf mit steigender Sequenzlänge, Timer-Option und Highscore-Verwaltung
- Visuelles und akustisches Feedback (optional per `playsound` oder macOS `afplay`)
- Umfangreicher wissenschaftlicher Projektbericht inklusive Literaturverweisen (`HCI_Projektbericht_….docx`)

## Voraussetzungen

- Python 3.11 oder höher
- Optional: `afplay` (macOS) oder `playsound` zur Musikwiedergabe

## Schnellstart

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows PowerShell

pip install -r requirements.txt
python src/color_memory.py
```

Beim ersten Start wird in `data/highscore.txt` automatisch ein Highscore-Datensatz erzeugt. Über den Button „Highscore zurücksetzen“ lässt sich der Wert löschen.

## Entwicklungsnotizen

- Das UI ist vollständig in `src/color_memory.py` implementiert und orchestriert den Spielablauf.
- Die Spiel-Logik (Sequenzen, Bewertung, Highscore) liegt gekapselt in `src/game.py`.
- Konfigurationen für Farben, Pfade und UI-Konstanten befinden sich in `src/config.py`.
- `src/audio.py` kümmert sich um Hintergrundmusik sowie kurze Feedback-Sounds.
- Hilfsfunktionen wie Pfadbehandlung sind in `src/utils.py` ausgelagert.

### Tests & Linting

Aktuell sind keine automatisierten Tests eingebunden. Für künftige Erweiterungen empfiehlt sich z. B. [`pytest`](https://docs.pytest.org/) für Logik-Tests sowie [`ruff`](https://docs.astral.sh/ruff/) zur Code-Qualität.

## Paketierung (PyInstaller)

Ein beispielhafter Build lässt sich mit PyInstaller erstellen:

```bash
pyinstaller --noconfirm --windowed --name EmojiColorMemory src/color_memory.py
```

Das Ergebnis landet im Verzeichnis `dist/` (unter macOS als `.app`, unter Windows/Linux als ausführbares Verzeichnis). Bei Bedarf können eigene `.spec`-Dateien erzeugt werden, um Assets oder Startparameter individuell zu konfigurieren.

## Assets & Daten

- `assets/logo.png` – Logo für Hauptmenü und Spielansicht
- `assets/music.wav` – Hintergrundmusik (optional)
- `data/highscore.txt` – Persistenter Highscore (JSON-basiert)

## Dokumentation

Der wissenschaftliche Bericht (`HCI_Projektbericht_FrankfurtUAS_ColorMemoryGame.docx`) dokumentiert Konzept, Implementierung, Evaluation sowie theoretische Grundlagen mit Literaturangaben. Das Vorlesungsskript von Prof. Deegener wird darin als Quelle referenziert, befindet sich aus urheberrechtlichen Gründen jedoch nicht im Repository.

## Lizenz

Bitte vor Veröffentlichung eine passende Lizenz ergänzen (z. B. MIT oder CC BY-SA je nach gewünschter Weitergabe).
