# Ardour Ultra MCP einrichten

[English](INSTALLATION.md) · [MCP-Clients](MCP_CLIENTS.md) · [Alle Dokumente](README.md)

Ardour Ultra MCP verbindet einen MCP-fähigen KI-Client mit Ardour. Der Server kann Sessions untersuchen und über Ardours echte Lua-Schnittstellen unter anderem MIDI-Noten, Plugin-Parameter, Mixer und Automation bearbeiten. Die Steuerung und Audioanalyse laufen lokal. Der Server benötigt keinen API-Schlüssel; dein gewählter Client und dessen Modell können eigene Voraussetzungen haben.

Folge den fünf Schritten der Reihe nach. Befehle gehören ins **Terminal** auf Linux/macOS beziehungsweise in **PowerShell** auf Windows. Du musst weder Git installieren noch selbst eine Python-Umgebung anlegen.

## Vor dem Start

- Ardour muss bereits installiert sein. Starte es einmal, damit sein Konfigurationsordner angelegt wird.
- Für die erste Einrichtung brauchst du Internet zum Herunterladen der Software.
- Halte einen MCP-Client bereit, der lokale STDIO-Server unterstützt, etwa Claude Desktop, Claude Code oder Codex.
- Verwende für den ersten Test eine neue, entbehrliche Ardour-Session.

**Aktueller Stand: Entwicklungsversion 0.1.0.** Ardour **9.8 unter Linux** wurde mit echten Integrationstests geprüft; **8.12** bietet einen kleineren geprüften Funktionsumfang. Die Python/MCP-Schicht besteht CI-Tests auf Linux, macOS und Windows. **Die native Ardour-Anbindung auf macOS und Windows ist noch nicht verifiziert.** Unter Windows sind insbesondere Lua-Heartbeat-Dateiersetzung und Berechtigungsprüfungen offen. Installation und Python-Tests sind kein Nachweis einer vollständig funktionierenden DAW-Anbindung. Details: [Kompatibilität](COMPATIBILITY.md).

## 1. uv installieren

uv installiert den Server in einer isolierten Umgebung und beschafft bei Bedarf Python. Wenn `uv --version` bereits funktioniert, kannst du diesen Schritt überspringen.

**Linux und macOS:**

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows PowerShell:**

```powershell
winget install --id=astral-sh.uv -e
```

Das sind Befehle aus der [offiziellen uv-Anleitung](https://docs.astral.sh/uv/getting-started/installation/). Dort findest du Alternativen, wenn `curl` oder `winget` fehlen. Bei Installationsskripten kannst du den Inhalt vor der Ausführung prüfen.

Schließe das Terminal und öffne ein neues. Prüfe:

```sh
uv --version
```

Es sollte eine Versionsnummer erscheinen.

## 2. Den MCP-Server installieren

Dieser Befehl funktioniert von jedem Verzeichnis aus und lädt den aktuellen Stand direkt von GitHub. Das Paket ist **noch nicht auf PyPI veröffentlicht**.

```sh
uv tool install --python 3.12 "ardour-ultra-mcp[analysis] @ https://github.com/Elias02345/ardour-ultra-mcp/archive/refs/heads/main.zip"
uv tool update-shell
```

Öffne danach ein neues Terminal:

```sh
ardour-ultra-mcp --version
```

Erwartet wird `ardour-ultra-mcp 0.1.0`. Wird der Befehl nicht gefunden, prüfe `uv tool dir --bin` und ob dieses Verzeichnis im PATH liegt. Führe bei Bedarf `uv tool update-shell` erneut aus und starte das Terminal neu.

`[analysis]` installiert die optionalen Bibliotheken für lokale Audioanalyse mit. Die direkte ZIP-Installation wurde unter Linux geprüft. Die uv-Befehle für macOS/Windows stammen aus der offiziellen Dokumentation; die native Installation wurde hier auf diesen Systemen nicht ausgeführt. `main` ist ein beweglicher Entwicklungsstand. Für einen festen Stand kannst du `refs/heads/main.zip` durch eine geprüfte Commit-SHA mit angehängtem `.zip` ersetzen.

## 3. Die Ardour-Bridge aktivieren

```sh
ardour-ultra-mcp install
```

Der Installer zeigt den Skriptpfad, das private Kommunikationsverzeichnis und die nächsten Schritte an. Er legt Backups an, aktiviert den Hook aber noch nicht.

Kann Ardour nicht automatisch erkannt werden, wählt der Installer **Version 9** und meldet das ausdrücklich. Nutzt du Ardour 8, verwende:

```sh
ardour-ultra-mcp install --ardour-major 8
```

Jetzt in Ardour:

1. Starte Ardour neu, falls es während der Installation geöffnet war. Öffne eine entbehrliche Session.
2. Öffne **Edit → Lua Scripts → Script Manager**.
3. Wähle den Reiter **Action Hooks**, klicke **New Hook**, wähle **Ardour Ultra MCP** und bestätige den Dialog.
4. Lass Ardour und die Session geöffnet.

Die englischen Bezeichnungen sind gegen den Quellcode von Ardour 9.8 geprüft. In älteren Versionen beziehungsweise im Handbuch heißt der Menüpfad möglicherweise **Scripted Actions → Manage**. In einer deutschen Oberfläche sind die Namen übersetzt. Der richtige Skripttyp ist **Action Hook**; er läuft im GUI-Kontext.

Die Bridge braucht Lua-Dateizugriff. Ardour 9.8 erlaubt diesen standardmäßig (`sandbox-all-lua-scripts=false`). Normalerweise musst du keine Einstellung ändern. Ein sichtbarer Preferences-Schalter wurde nicht nachgewiesen. Falls du die Lua-Sandbox selbst aktiviert hast, siehe [Fehlerhilfe](TROUBLESHOOTING.md#lua-file-io-is-blocked). Eine Änderung betrifft alle Lua-Skripte: Aktiviere nur geprüfte, vertrauenswürdige Skripte. Der Installer verändert diese Einstellung nicht.

## 4. Die Verbindung prüfen

```sh
ardour-ultra-mcp test-connection
ardour-ultra-mcp doctor
```

Erwartet wird bei der ersten Prüfung:

```text
Connection OK: the Ardour Lua bridge responds.
Session: open
```

Beide Befehle sollen erfolgreich enden (Exit-Code `0`). Bei einer fehlenden Verbindung nennt die Ausgabe den Fehler und einen nächsten Schritt; Exit-Code `2` bedeutet ein Problem. Ein gestoppter Audio-Engine-Status verhindert nicht zwingend die Bridge-Verbindung. Für Wiedergabe und Export muss Ardours Audio-Engine passend eingerichtet sein.

Falls es noch nicht klappt:

- **BRIDGE_NOT_RUNNING:** Session geöffnet? Hook unter **Action Hooks** hinzugefügt? Nach einer Neuinstallation den alten Hook entfernt und neu hinzugefügt?
- **Skript fehlt in der Auswahl:** Ardour neu starten und den gedruckten Skriptpfad prüfen. Bei einer eigenen Installation den richtigen Ordner mit `install --ardour-config "/absoluter/Pfad/Ardour9"` wählen.
- **Falsches Kommunikationsverzeichnis:** Falls du `--mailbox` verwendest, muss derselbe Pfad bei Installation, Verbindungstest, Doctor und Client-Konfiguration stehen.
- **Timeout nach einer Änderung:** Die Änderung könnte trotzdem ausgeführt worden sein. Erst den tatsächlichen Zustand prüfen, nicht blind wiederholen.

Mit `--json` erhältst du maschinenlesbare Diagnosen. Weitere Fälle stehen in [Troubleshooting](TROUBLESHOOTING.md).

## 5. Einen MCP-Client verbinden

Wähle **einen** Client. Dein Client startet den Server automatisch. Du musst `serve` normalerweise nicht in einem separaten Terminal laufen lassen.

### Claude Desktop

```sh
ardour-ultra-mcp configure claude
```

Öffne in Claude Desktop **Settings → Developer → Edit Config**. Sichere die bisherige Datei. Ist sie leer, füge die gesamte ausgegebene JSON-Konfiguration ein. Sonst ergänze nur den Eintrag `ardour-ultra` im bestehenden `mcpServers`-Objekt. Überschreibe keine anderen Server und lege keinen zweiten `mcpServers`-Schlüssel an. Speichere und starte Claude Desktop vollständig neu.

Typische Datei: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows `%APPDATA%\Claude\claude_desktop_config.json`. Eine Linux-Version von Claude Desktop wird nicht vorausgesetzt.

### Claude Code

Für die Standardinstallation:

```sh
claude mcp add --transport stdio --scope user ardour-ultra -- ardour-ultra-mcp serve
claude mcp list
```

Bei eigenen Pfaden oder einem eingeschränkten PATH nutze `ardour-ultra-mcp configure claude-code` und ergänze den ausgegebenen Eintrag in der Projektdatei `.mcp.json`. Wähle einen der beiden Wege, um doppelte Registrierungen zu vermeiden. Starte eine laufende Claude-Code-Session neu.

### Codex

Für die Standardinstallation:

```sh
codex mcp add ardour-ultra -- ardour-ultra-mcp serve
codex mcp list
```

Alternativ druckt `ardour-ultra-mcp configure codex` einen TOML-Abschnitt mit absolutem Programmpfad. Sichere `~/.codex/config.toml` und ergänze nur diesen Abschnitt. Eine Tabelle darf nicht zweimal definiert werden. Wähle einen Einrichtungsweg und starte die Codex-Session neu.

### Andere STDIO-Clients

`ardour-ultra-mcp configure generic` druckt ein `mcpServers`-JSON. Unterstützt dein Client ein anderes Format, übertrage `command` und `args` in seine STDIO-Einstellungen. Du brauchst keine HTTP-Adresse und keinen Netzwerkport.

`configure` druckt nur die Konfiguration und verändert keine Dateien. Die Formate folgen den offiziellen Client-Anleitungen. Die Client-Anwendungen selbst wurden hier nicht als E2E-Test gestartet; getestet wurde der offizielle Python-MCP-Client. [Weitere Details und Quellen](MCP_CLIENTS.md).

## Der erste Auftrag

Wenn dein Client die Tools erkannt hat, beginne mit:

> Prüfe mit Ardour Ultra MCP die Verbindung, die Session und die verfügbaren Fähigkeiten. Liste die Tracks und nicht unterstützte Funktionen auf. Verändere noch nichts.

Die Einrichtung ist abgeschlossen, wenn der Verbindungstest und Doctor erfolgreich sind und der Client die Tools findet. Einen kontrollierten ersten MIDI-Track-Test beschreibt der [Quick Start](QUICK_START.md). Vor Änderungen an echter Arbeit: Session sichern und Fähigkeiten des laufenden Backends prüfen.

## Optional: Audioanalyse und Export erlauben

Für den Einstieg ist das nicht erforderlich. Lege zunächst einen eigenen Projektordner und einen Export-Elternordner an. Nur ausdrücklich freigegebene absolute Pfade dürfen benutzt werden.

```sh
ardour-ultra-mcp install --export-root "/absoluter/Projektpfad/exports"
ardour-ultra-mcp configure codex --media-root "/absoluter/Projektpfad" --export-root "/absoluter/Projektpfad/exports"
```

Ersetze `codex` durch deinen Client und die Beispielpfade durch vorhandene Ordner. Unter PowerShell sind beispielsweise `"C:\Music Projects\Reel"` und `"C:\Music Projects\Reel\exports"` passende Pfade. Nach der Neuinstallation den alten Hook entfernen und neu hinzufügen, die aktualisierte Client-Konfiguration übernehmen und den Client neu starten.

Installer und Server brauchen übereinstimmende Exportfreigaben. Jeder Export schreibt in einen **neuen Unterordner**; vorhandene Ziele werden abgelehnt. Master-Export ist experimentell und nutzt ein vorhandenes Ardour-Exportpreset. Stems und beliebige Formatänderungen sind noch nicht implementiert. [Audioanalyse](AUDIO_ANALYSIS.md).

## Aktualisieren

1. Sichere deine Session und schließe den MCP-Client.
2. Entferne den Hook in Ardours Script Manager und schließe Ardour.
3. Aktualisiere den Server und installiere die Bridge erneut:

```sh
uv tool install --reinstall --python 3.12 "ardour-ultra-mcp[analysis] @ https://github.com/Elias02345/ardour-ultra-mcp/archive/refs/heads/main.zip"
ardour-ultra-mcp install
```

4. Wiederhole dabei deine ursprünglichen Optionen für `--ardour-major`, `--ardour-config`, `--mailbox` und `--export-root`. Ohne Export-Option setzt eine Neuinstallation die Exportfreigaben zurück.
5. Öffne Ardour, füge den Hook neu hinzu, prüfe die Verbindung und starte deinen Client neu.

Ardour speichert kompilierte Hooks. Nur die Skriptdatei zu ersetzen lädt den laufenden Hook nicht neu. Bewahre die Installer-Backups auf, bis du das Update geprüft hast.

## Entfernen

Entferne zuerst den Hook in Ardour und schließe den MCP-Client. Dann:

```sh
ardour-ultra-mcp uninstall
uv tool uninstall ardour-ultra-mcp
```

Entferne anschließend nur den Ardour-Eintrag aus der Client-Konfiguration. Bei einem eigenen Mailbox-Pfad musst du ihn auch bei `uninstall` angeben. Mailbox und Backups bleiben zur Prüfung erhalten. Ein von dir verändertes Skript wird nicht automatisch gelöscht; Sessions und Audio bleiben erhalten.
