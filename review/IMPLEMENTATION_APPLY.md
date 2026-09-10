# Übernahme des vervollständigten Kandidaten

GitHub ist die maßgebliche Quelle. Der Kandidat erweitert den veröffentlichten
Commit e3fda1c1a78f5052253b28e3626f5f78d13a9ea5. Vor einem Merge die tatsächlichen
Prüfergebnisse des Kandidaten in Validate OSMS Catalog und Recipe CI prüfen.
Ein fehlendes oder fehlgeschlagenes Pflichtgate verhindert die Veröffentlichung.

Alle 119 bisher fehlenden zusätzlichen Profile sind implementiert. Der Export
enthält insgesamt 327 Karten und acht Dialekte. Quelle, generiertes Profilpaket
und Ausführungsberichte müssen denselben Hash tragen. Native Ausführung und
Quellenadapter werden getrennt von der Codegenerierung bewertet.

Bestehende Issues behalten ihre Audit-ID, Kategorie, Severity und Karten-IDs.
Nur erfüllte Abnahmekriterien schließen; echte Fix-Commit-SHAs und Prüfnachweise
im Issue ergänzen. Teilfixe, Pilot-/Mappingreviews, Website-Deployment und spätere
Boardaufgaben bleiben mit konkretem Restumfang sichtbar. F-28: extern bearbeitet.

Nach erfolgreicher Übernahme den generierten Katalog-/Profilstand für die externe
Website-Integration bereitstellen. Eine neue Version über das geschützte
Releaseverfahren mit tatsächlichen CI-Artefakten veröffentlichen. Vorhandene
Tags nicht verschieben. Details: RELEASE_0.9.2.md und EXECUTION_VALIDATION.md.
