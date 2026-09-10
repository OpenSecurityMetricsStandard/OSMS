# OSMS – Änderungen nach dem Audit vom 10.09.2026

Umgesetzt auf dem Arbeitsbranch `audit/remediation-2026-09-10`, ausgehend von
`747cd28fb0b6728ebadbe6c477722d166b5b40b5`. Dies ist ein prüfbarer Entwurf; er wurde weder auf GitHub gepusht noch veröffentlicht.

Die Arbeit behebt bestätigte technische Fehler und setzt ausgewählte fachliche Grenzwertvorschläge konkret um. Sie schließt nicht pauschal alle 32 Auditbefunde. Insbesondere Confidence-Produktion, Normalisierung, Risikomodelle, Governance und vollständige Konformität aller 327 Karten bleiben offen.

## Wesentliche Änderungen

- MTTD nach Detection-Periode und Bestätigung am Stichtag; exakter Median/P90 und Severity-Gewichte.
- SLA-Behandlung berücksichtigt Remediation oder validierte Mitigation; leere Zeitstempel werden nicht als Erfolg gewertet.
- Composite- und DSPS-Prüfungen lehnen fehlende Werte, problematische Gewichte und doppelte Penalty-IDs ab.
- Referenzarithmetik und SQL-Views prüfen Beiträge erneut, behalten fehlende Evidenz sichtbar und unterscheiden begrenzte Arithmetikprüfung von Kartenkonformität.
- Green setzt einen gültigen Zustand und bekannte ausreichende Confidence voraus; unbekannte Drill-Achsen und unvollständige Rezeptvorlagen liefern kein falsches OK.
- Review-KPIs, vollständiger Kartenexport, Prüfumgebung, Release-Prüfungen und Dateimanifeste verbessert.

## Versions- und Übernahmehinweise

Katalogbasis bleibt 0.9.1, `release_phase` ist `working_draft`. Die sieben geänderten Karten STD-005/012/015/019/055, SOC-063 und STD-016 tragen `card_version: 0.9.2-draft`. Sechs davon enthalten bewusst vorgeschlagene Grenzwertentscheidungen; STD-016 ergänzt `mitigated_at`. Bestehende Loader und Datenbanken benötigen die dokumentierten Adapter-/Schemaanpassungen. Das neue Schema-URI ist eine Kandidatenkennung, keine Behauptung einer bereits erreichbaren Webveröffentlichung.

Status- und API-Änderungen: `curated_candidate` ersetzt die ungeprüfte Aussage `curated_verified`; Mapping-Fehler sind explizit; SQL-Reconciliation verwendet differenzierte Zustände statt eines universellen OK. Das lokale Release-Werkzeug baut ein Quellarchiv und veröffentlicht nichts. Die automatische stabile 1.x-Promotion bleibt bis zu einer übernommenen Freigaberegel gesperrt.

## Prüfungen

Die ausführbaren Regressionen liegen in `tests/test_remediation.py`. Ergebnisse und konkret nicht ausgeführte Engines stehen in `review/VALIDATION.md`. Die Zahl der Kandidatenfixtures ist von 14 auf acht reduziert: sechs unvollständige Dauer-Templates bleiben mit Beispielen vorhanden, zählen aber nicht mehr als implementierte Karten. Dies ist offengelegte fehlende Abdeckung, keine neu gewonnene Vollkonformität.

## Alle Auditbefunde

„Implementiert“ bezeichnet die konkrete technische Korrektur im beschriebenen Umfang; es ersetzt weder eine Anwendungsprüfung noch einen unabhängigen Board-Review.

| ID | Befund | Stand und Restarbeit |
|---|---|---|
| F-01 | Rechenfamilien nach mathematischer Bedeutung trennen | **Teilweise**: Allgemeine Quotienten von Anteilen abgegrenzt; HRM-004 unskaliert und >1 geprüft. Vollständige Methodenprofile fehlen. |
| F-02 | Referenz-Engine führt kartenspezifische Formeln nicht aus | **Teilweise**: STD-005, STD-074, Einheitenumrechnung und Penalty-Caps korrigiert; die Engine behauptet keine vollständige Kartenkonformität. |
| F-03 | Median und Perzentilmethode pro Ausgabe verbindlich machen | **Teilweise**: SOC-002-Median/P90 präzisiert; unvollständige Dauerrezepte gesperrt. Weitere Ausgabeprofile und reale Fremd-Engines offen. |
| F-04 | MTTD-Rezept verwendet die falsche Fallbasis | **Teilweise**: MTTD-Fallbasis, Bestätigung und Severity-Gewichte in SQL/Python/Excel korrigiert. ES|QL gesperrt; DAX liefert weiterhin nur die dokumentierte P90-Teilimplementierung. |
| F-05 | SLA-Rezept bildet validierte Mitigation nicht ab | **Implementiert**: Mitigation als zusätzlicher nullable Eingang; fristgerechte Behandlung alternativ geprüft, leere Datumswerte zählen nicht. Adaptermigration und echte DAX/SPL/ES-Ausführung bleiben Anwendungspflichten. |
| F-06 | Composite-Rezepte akzeptieren fehlende Werte und negative Gewichte | **Teilweise**: NULL/NaN/Inf, negative Gewichte, IDs und Excel-Zelltypen abgesichert. Vollständige Profil-/Versionsbindung sowie Fremd-Engine-Gegenproben fehlen. |
| F-07 | DSPS-Penalty-Gates prüfen nicht die Identität beider Abzüge | **Teilweise**: Beide Penalty-IDs, Duplikate, fehlende Werte und Caps geprüft. Perioden-, Normalisierungs- und Versionsbindung bleibt offen. |
| F-08 | Datenbank erlaubt Grün bei unbekannter Confidence und n/a | **Implementiert**: SQL blockiert Green bei unbekannter Confidence, n/a, provisorischem Zustand und unter 70/85; negative Nenner werden abgewiesen. Für bestehende Datenbanken ist eine Migration nötig. |
| F-09 | Confidence-Produktion benötigt numerische, nicht kompensierbare Regeln | **Offen – Fachentscheidung**: Konkrete numerische Confidence-Profile und nicht kompensierbare Gates werden nicht erfunden; Entscheidungsvorlage vorhanden. |
| F-10 | Reconciliation prüft gespeicherte Beiträge statt unabhängiger Ableitung | **Teilweise**: Gewicht × Eingang wird neu berechnet; Cache-, Kindwert-, Scope- und Evidenzabweichungen werden erkannt. Authentizität und Normalisierungsnachweis offen. |
| F-11 | SQL-Reconciliation meldet falsche Fehler und übersieht fehlende Evidenz | **Teilweise**: Gewichteter Mittelwert und fehlende Evidenz korrigiert; allgemeine Ratios geben ADAPTER_REQUIRED statt eines falschen OK. Vollständige typisierte Reconciliation offen. |
| F-12 | Scope- und Versionsbindung bei Drill und Ranking schließen | **Teilweise**: Exakte Katalogversion und Scope gebunden, Current-View korrigiert. Ranking bestätigt keine tautologische Selbstsortierung mehr; echtes Ranking-Modell fehlt. |
| F-13 | Rechentoleranz nach Einheit und Operator festlegen | **Teilweise**: Count wird exakt, Rohwertarithmetik enger geprüft. Vollständige Toleranzprofile pro Einheit/Ausgabe noch offen. |
| F-14 | Semantische Validatorversprechen durch echte Prüfungen ersetzen | **Teilweise**: Zyklen, Selbstbezüge, Literaldivision durch null, ausgewählte Composite-Beispiele und Leertext-Owner geprüft; überzogene Prüfaussagen korrigiert. Kein Vollparser für alle Formeln. |
| F-15 | Testabdeckung als Konformitätsmatrix statt Gesamt-PASS ausweisen | **Teilweise**: Unabhängige Regressionen und ehrliche Populationszahlen ergänzt; acht numerische Kandidatenfixtures separat von sechs zurückgestellten Template-Beispielen. Vollständige Konformitätsmatrix fehlt. |
| F-16 | Ausführbare Skeletons dürfen keine plausiblen Standardwerte liefern | **Implementiert**: Unfertige Rezepte geben keine plausiblen KPI-Werte aus; Vorlagen bleiben zum Implementieren erhalten. |
| F-17 | Release und Rezeptveröffentlichung an nachgewiesene Gates binden | **Teilweise**: PR- und Tag-Prüfungen erweitert, Draft-Release-Sperre eingebaut. Stabile Promotion verlangt eine noch zu implementierende Board-/Engine-Evidenzfreigabe. |
| F-18 | Ampelregeln lückenlos, disjunkt und priorisiert definieren | **Entscheidungsvorschlag implementiert**: Sechs Karten erhalten lückenlose Entwurfsgrenzen und ausführbare Grenzwertprofile; bewusst zur fachlichen Bewertung, nicht als Boardbeschluss. |
| F-19 | Posture-Normalisierung global nachvollziehbar machen | **Offen – Fachentscheidung**: Normierungsfunktionen und eingefrorene Gewichtsprofile müssen pro Kind/Ausgabe festgelegt werden. |
| F-20 | Feldnamen und Mehrfachausgaben zu ausführbaren Datenverträgen ergänzen | **Teilweise**: Ausführungsvertrag, Zustände und zusätzliche Behandlungsspalte dokumentiert; vollständige typisierte Ein-/Ausgaben aller 327 Karten fehlen. |
| F-21 | Lineage-Anforderungen und offene Referenzrubriken vollständig bereitstellen | **Teilweise**: Unbekannte Drill-Achsen lösen Fehler aus. Vollständige Achsenregistrierung, Pfadtiefe und offene Rubriken bleiben offen. |
| F-22 | Messgröße und Kennzahlname auf dieselbe Aussage begrenzen | **Offen – Fachentscheidung**: Konstrukt-/Namensentscheidungen für SOC-023, AIM-011 und SOC-072 dokumentiert; kein stiller Definitionswechsel. |
| F-23 | Stichprobenunsicherheit und Selektionsbias separat ausweisen | **Offen – Fachentscheidung**: Stichproben-/Selektionsunsicherheit separat vorgesehen; keine pauschalen Intervalle oder erfundenen Pilotdaten. |
| F-24 | Verteilungs- und Risikomodelle operational spezifizieren | **Offen – Fachentscheidung**: Risikomodellprofile und mögliche Doppelzählung STD-056 benötigen methodische Entscheidung. |
| F-25 | Review-KPI-Skript an das eigene Review-Verfahren angleichen | **Teilweise**: GitHub-IDs, Kommentare, Entscheidungen, vollständige Pagination, Werktage und K-09-Evidenz verbessert. Personen-Aliase, Nicht-GitHub-Importe und Charterdefinition benötigen zusätzliche Daten. |
| F-26 | Boardfreigabe als nachvollziehbare Entscheidung definieren | **Offen – Governance**: Board im Aufbau; Kandidatenbaseline, Zeitplan, Charter und Gate-Kombination müssen übernommen werden. Keine Freigabe simuliert. |
| F-27 | Framework-Mappings als begründete Beziehungen pflegen | **Offen – Fachentscheidung**: Edition/Beziehung/Begründung der Framework-Mappings bleiben Aufgabe; keine Behauptung von ISO-Konformität. |
| F-28 | Website-Schema und GitHub-Vertrag eindeutig versionieren | **Teilweise**: Alle Kartenfelder im Website-Export; eigene Schema-ID für den Draft. Live-Webseite und separates Frontend sind nicht aktualisiert. |
| F-29 | Auswertungsversion und Freigabepaket vollständig historisieren | **Teilweise**: Quellarchiv mit vollständigem Einzeldateimanifest und Kataloghash im Rezeptbundle. Vollständiges Auswertungsmanifest mit Daten-/Profil-/Engine-Nachweisen bleibt offen. |
| F-30 | Formale Dokumentations- und Lizenzgrenzen konsolidieren | **Teilweise**: Dokumentation, historische Termine und Validatorversprechen bereinigt. Endgültige Rechte-/Lizenzmatrix für alle Bestandteile noch zu bestätigen. |
| F-31 | Abhängigkeiten und Testumgebung reproduzierbar festlegen | **Teilweise**: Direkte Python-Abhängigkeiten und Kusto-Paketversion fixiert. Transitive Locks, Action-SHAs und vollständige Engine-Matrix offen. |
| F-32 | Board-Review nach Risiko und Prüftiefe organisieren | **Offen – Governance**: Risiko- und Prüftiefenplanung benötigt tatsächliche Board-Mitglieder; keine Zuordnungen oder Termine erfunden. |

Details: [Methodenentscheidungen](METHOD_DECISIONS.md), [Rechenverträge](../recipes/CONTRACTS.md), [Review-KPI-Methode](REVIEW_KPI_METHOD.md).
