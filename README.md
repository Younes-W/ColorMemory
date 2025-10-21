# Color Memory

Ein modernes Farbgedächtnis-Spiel mit einer CustomTkinter-Oberfläche. Das Spiel zeigt nacheinander Farbwörter an, die sich in Schrift- und Hintergrundfarbe unterscheiden. Merke dir die Reihenfolge der Wörter und gib sie anschließend korrekt ein, um in die nächste Runde zu gelangen.

## Features
- Ansprechende UI auf Basis von [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- Highscore-Verwaltung mit lokaler Speicherung unter `data/highscore.txt`
- Optionale Hintergrundmusik (`assets/music.wav`)
- Animierte Rückmeldungen, Timer-Modus und Hotkeys für einen flüssigen Spielfluss

## Voraussetzungen
- Python 3.11 oder höher
- macOS, Windows oder Linux mit einer installierten Tcl/Tk-Laufzeit (standardmäßig in der regulären Python-Installation enthalten)

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows PowerShell

pip install -r requirements.txt
```

## Spiel starten
```bash
python src/color_memory.py
```

Die Highscore-Datei (`data/highscore.txt`) wird beim ersten Start automatisch erstellt und kann zurückgesetzt werden, indem du im Spiel den Button „Highscore Reset“ verwendest oder die Datei manuell auf `0` setzt.

## Musik aktivieren
Das Spiel versucht, Musik mit `afplay` (macOS) oder der Bibliothek `playsound` abzuspielen. Stelle sicher, dass `assets/music.wav` vorhanden ist. Auf anderen Betriebssystemen wird ein akustisches Signal über die Systemlautsprecher ausgegeben.

## App-Build (PyInstaller)
Ein vorkonfiguriertes PyInstaller-Skript liegt in `abgabe.spec`. Du kannst eine lauffähige `.app` (macOS) bzw. ein ausführbares Paket wie folgt erstellen:
```bash
pyinstaller --noconfirm abgabe.spec
```
Das fertige Bundle befindet sich anschließend im Ordner `dist/`.

## Projektstruktur
```
assets/          # Statische Ressourcen wie Logo und Musik
data/            # Persistente Daten (Highscore)
src/             # Python-Quellcode
abgabe.spec      # PyInstaller-Konfiguration für den App-Build
requirements.txt # Python-Abhängigkeiten
```

## Lizenz
Wähle beim Erstellen deines GitHub-Repositories eine passende Lizenz (z. B. MIT, Apache 2.0 oder GPL) und ergänze sie hier.
