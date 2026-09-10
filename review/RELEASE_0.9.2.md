# OSMS 0.9.2 — Maintainer-Entwurf

Der Maintainer kann OSMS vor Beginn des Review Boards korrigieren und 0.x-Versionen
veröffentlichen. Maßgeblich sind REVIEW_PROCESS.md, der identifizierte Quellcommit
und dessen tatsächliche Prüfnachweise. Ein vorbereitetes Paket oder Merge ist
noch keine Release-Veröffentlichung; GitHub Releases dokumentiert diese.

## Änderungen und Migration

Alle 327 Karten besitzen zusätzliche Implementierungen auf den acht bisherigen
Dialekten: 207 Quotientenprofile, 119 vorbereitete Beobachtungsprofile und ein
SOC-003-Snapshotprofil. Die Profile enthalten benannte Ausgaben, Einheiten,
Toleranzen, Eingangsdomänen, Versionsbindung, Scope/Periode, Evidenzfelder sowie
Regeln für leere, unvollständige und ungültige Daten. Excelvorlagen enthalten
Eingabe- und Hilfsbereiche sowie Kapazitätsprüfungen. Quellenadapter müssen die
jeweilige Grundgesamtheit und Rohdatenherkunft nachweisen.

125 geänderte Kartendefinitionen verwenden card_version 0.9.2; 201 behalten 0.9.1
und eine 0.9.0. Alle 327 Karten haben lifecycle: draft und 48 Quellfelder. Der
Katalog bezeichnet den enthaltenen Standard als 0.9.2/working_draft. Eigenständige
unveränderte Komponenten behalten ihre Version. SEMANTIC_CARD_CHANGES.json führt
die 119 erweiterten Kartendefinitionen einzeln auf.

Die Änderungen korrigieren unter anderem Dauer-Kohorten und Perzentile,
Normalisierung und DSPS-Rollups, Confidence, Penalties, Ranking, Mehrfachausgaben,
Risiko- und Surveyprofile. METHOD_DECISIONS.md dokumentiert fachliche Präzisierungen.
Neue Auswertungsprofile nicht still auf historische Reihen anwenden: Version,
Einheit, Normalisierungsanker, Parameterprofil und Quellenadapter gemeinsam binden.
STD-016 verwendet nullable mitigated_at und die am Periodenende gültige Validierung.
Bestehende Datenbanken benötigen die Migrationen aus recipes/CONTRACTS.md.

Historische Reports behalten ihre eingefrorenen Rechenprofile und Eingänge.
Manifest-Replay erkennt fehlende oder manipulierte Nachweise; die aktuelle
Katalogversion überschreibt keine historische Berechnung.

## Prüfung und offene Evidenz

EXECUTION_VALIDATION.md beschreibt die lokalen Ergebnisse und ihre Grenzen.
Die GitHub-Workflows liefern die tatsächlichen Ergebnisse des jeweiligen Commits.
Release-Pakete verlangen beide erfolgreichen Pflichtworkflows genau dieses
Commits und übernehmen die passenden Ausführungsnachweise in das Dateimanifest.
Kusto/DAX benötigen native Umgebungen; Microsoft Excel wird nicht durch formulas
oder LibreOffice als geprüft ausgegeben. Individuelle Quellenadapter und echte
Pilotdaten bleiben Anwendungsevidenz.

F-05/#6, F-08/#9 und F-18/#19 wurden bereits geschlossen. Weitere Schließungen
richten sich nach den einzelnen Abnahmekriterien und tatsächlichen Prüfnachweisen.
IMPLEMENTATION_CANDIDATE.json enthält Kategorie, Severity, Karten-IDs und
Teil-/Restumfang. GitHub führt die tatsächlichen Fix-Commits und Entscheidungen.
Historische Importdaten werden nicht als aktueller Nachweis umgeschrieben.

Das Framework-Register kennzeichnet 1.149 Zuordnungen ausdrücklich als nicht
bewertet. Es verlangt Edition, Beziehung, Begründung und echten Reviewbeleg für
jede geprüfte Zuordnung. F-28 wird nach Repository-Aktualisierung extern bearbeitet;
der Schema-URI beweist kein Website-Deployment. Pilotbelege und die spätere
Boardbesetzung/-Charter werden eingetragen, sobald sie vorliegen. Sie werden
nicht aus Testdaten oder technischen Prüfläufen abgeleitet.
