# Prüfung der vervollständigten Rechenprofile

Stand: 10.09.2026. Dieser Kandidat baut auf
`e3fda1c1a78f5052253b28e3626f5f78d13a9ea5` auf. Der Basis-Commit ist kein
Fix-Nachweis der zusätzlichen Änderungen. GitHub führt die tatsächlichen
Kandidaten-Commits, CI-Ergebnisse und Issue-Dispositionen.

## Umfang

Alle 327 Karten besitzen zusätzliche Rechenprofile: 207 kanonische Quotienten,
119 typisierte Profile für die übrigen Rechenfamilien und SOC-003 als eigenes
Incident-Snapshot-Profil. Die Matrix umfasst 2.616 Karten-/Dialektzeilen für
Python, DuckDB, PostgreSQL, KQL, SPL, ES|QL, Excel und DAX. ES|QL verwendet bei
exakten Mehrfachausgaben einen vollständigen Export mit exakter Python-Reduktion.
Quellenadapter und die Bestätigung einer vollständigen Grundgesamtheit bleiben
explizite Anwendungspflichten. Die Profile rechnen nicht aus unbestätigten Daten
stillschweigend ein erfolgreiches Ergebnis.

125 Kartendefinitionen tragen Version 0.9.2, 201 behalten 0.9.1 und eine 0.9.0.
Alle 327 Karten haben 48 Quellfelder einschließlich `lifecycle: draft`.
Die 119 ergänzten Karten sind in SEMANTIC_CARD_CHANGES.json einzeln dokumentiert.

## Lokale Nachweise vor nativer CI

| Prüfung | Beobachtetes Ergebnis | Aussagegrenze |
|---|---|---|
| Regressionen | 87 Tests bestanden; vier zusätzliche Risiko-/Mappingtests bestanden | Synthetische und strukturelle Gegenproben |
| 119 vorbereitete Beobachtungsprofile, Python 3.12.14 | 1.548 Fälle bestanden | Kein Nachweis produktiver Quellenadapter |
| Dieselben 119 Profile, DuckDB 1.5.5 | 1.548 Fälle bestanden | Eigenständige SQL-Ausführung |
| 119 vorbereitete Beobachtungsprofile, formulas 1.3.4 | 1.548 Fälle bestanden | Excel-Formelauswertung; kein Microsoft-Excel-Nachweis |
| 207 Quotienten, Python | 3.726 Fälle bestanden | Kanonische Eingänge |
| 207 Quotienten, DuckDB | 3.726 Fälle bestanden | Kanonische Eingänge |
| 207 Quotienten, formulas 1.3.4 | 1.035 Fälle bestanden | Fünf benannte Fälle je Karte; kein Microsoft-Excel-Nachweis |
| KQL-Sprachdienst 12.4.1 | 326 zusätzliche Abfragen bestanden | Syntax und Typen; keine native Kusto-Ausführung |
| Katalogvalidator | 327 Karten, 0 Fehler, 0 Warnungen | Umgesetzte Prüfregeln, kein vollständiger Freitext-Beweiser |
| Framework-Register | 1.149 eindeutige Zuordnungen, alle ausdrücklich nicht bewertet | Keine erfundenen Editionsprüfungen oder Konformitätsaussagen |
| Synthetisches Risikomodell | Vier reproduzierbare Szenarien à 100.000 Ziehungen; unabhängige analytische Poisson-Gegenproben | Keine empirische Kalibrierung |

Diese vollständigen lokalen Rechenläufe verwenden Profilpaket
`52afda9c87e3dc1d490bea2db4cd3d21d028b8d4e9e9ad1ade0c17e7fd19e4f7`.
Anschließend wurden ausschließlich die SPL-/DAX-Ranking-Statusausgaben ergänzt;
die oben genannten numerischen Python-/DuckDB-/Excel-Ausdrücke sind unverändert.
Der vollständige Excel-Formellauf der 119 Profile ist ebenfalls bestanden.
Python (1.548 Fälle) und der KQL-Analyzer (326 Jobs) wurden danach auch auf dem
aktuellen Kandidatenpaket erfolgreich wiederholt. Native CI-Läufe werden über
ihre tatsächlichen Berichte bewertet, nicht aus der Generierung abgeleitet.

Aktuelles Kandidatenpaket: `8a3ed49a5a58a1230b5f55df4fca3e2eb3dd439dfdaba4d93fc0428c2d00d3ed`.
Ausführungsberichte werden nur bei exakt passendem Paket- und Quellhash in die
Konformitätsmatrix übernommen. Vorherige Berichte werden nicht umetikettiert.

## CI und Release

Recipe CI führt die 119 Profile in Python, DuckDB, formulas, PostgreSQL,
LibreOffice und über nativen ES|QL-Export aus; SPL läuft gemäß vorhandener
Repository-Konfiguration. Native Kusto-, DAX- und Microsoft-Excel-Nachweise bleiben
separat erforderlich. LibreOffice ist eine zweite Tabellenkalkulation, kein
Microsoft-Excel-Nachweis. Syntaxprüfung zählt nicht als numerische Ausführung.

Die Veröffentlichung verlangt erfolgreiche Pflichtworkflows genau des
Release-Commits sowie passende numerische Engineberichte. Fehlende, laufende,
fehlgeschlagene oder veraltete Nachweise blockieren das Paket. Das Releasearchiv
enthält die tatsächlichen CI-Nachweise und ein vollständiges Dateimanifest.
Synthetische Daten werden durchgehend als solche bezeichnet.

Historische Auswertungen frieren Profil, Parameter, Beobachtungen, Ergebnis und
Interpreteridentität ein. Ein separat aufzubewahrender Manifest-Hash bindet die
Wiederherstellung; fehlende oder veränderte Dateien werden auch dann erkannt,
wenn die Gesamtsumme unverändert bleibt.

F-23 benötigt echte Pilotbelege, F-27 begründete Mappingreviews, F-28 wird nach
Repository-Übernahme extern bearbeitet. F-26/F-32 betreffen den späteren formalen
Boardprozess. Diese Abhängigkeiten werden nicht als technische PASS-Ergebnisse
verbucht. Aktuelle Zuordnung: IMPLEMENTATION_CANDIDATE.json und GitHub-Issues.
