# Safe Bet – Einrichtung (ca. 30 Minuten, einmalig)

## 1. Repository anlegen (am PC)
1. Auf github.com oben rechts **+ → New repository**.
2. Name: `tipp-das`, Sichtbarkeit **Public** (GitHub Pages ist nur für öffentliche Repos kostenlos). Nichts weiter ankreuzen, **Create repository**.
3. Auf der leeren Repo-Seite **uploading an existing file** anklicken.
4. Diese Dateien aus dem entpackten Ordner reinziehen: `build.py`, `index.html`, `manifest.json`, `sw.js`, `requirements.txt`, `icon-192.png`, `icon-512.png`. **Commit changes**.
5. Die Steuerdatei separat anlegen, weil Windows den Ordner `.github` beim Hochladen gern verschluckt:
   **Add file → Create new file**, als Namen genau `.github/workflows/update.yml` eintippen (die Schrägstriche legen die Ordner an), den Inhalt der Datei `update.yml` aus dem Paket hineinkopieren, **Commit changes**.

## 2. Seite einschalten
1. Im Repo **Settings → Pages**.
2. Bei **Source** „GitHub Actions“ wählen.
3. Oben auf **Actions** → links „Daten aktualisieren“ → **Run workflow** → **Run workflow**.
4. Nach 2–4 Minuten ist der Lauf grün. Deine App liegt dann unter
   `https://DEIN-GITHUB-NAME.github.io/tipp-das/`

Ein roter Lauf direkt nach Schritt 1.5 ist normal, da war Pages noch aus. Zählt nur der Lauf aus Schritt 2.3. Falls der rot ist: draufklicken, den roten Schritt aufklappen und mir die Meldung schicken.

## 3. Token für den Button erstellen
1. Oben rechts auf dein Profilbild → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Name: `tipp-das`, Ablauf: 1 Jahr.
3. **Repository access:** „Only select repositories“ → `tipp-das`.
4. **Permissions → Repository permissions → Actions:** „Read and write“. Sonst nichts.
5. **Generate token** und den Token (beginnt mit `github_pat_`) kopieren, z. B. per Mail an dich selbst.

Der Token darf nur diese eine Berechnung starten. Damit kann niemand an deinen Code oder dein Konto.

## 4. Aufs Handy holen
1. Die Adresse aus Schritt 2 in **Chrome** öffnen.
2. Menü **⋮ → App installieren** (oder „Zum Startbildschirm hinzufügen“).
3. App öffnen, ganz unten **Einstellungen** aufklappen, Token einfügen, **Token speichern**.

## So nutzt du sie
- Die Daten aktualisieren sich jeden Sonntag um 11:00, 17:00, 18:43 und 21:48 Uhr von selbst (GitHub startet manchmal ein paar Minuten später).
- **Daten aktualisieren** startet sofort eine neue Berechnung, nach 2–4 Minuten lädt die Seite die neuen Werte.
- Beste Zeit: Sonntag ab 17:00 Uhr. Dann stehen Verletzungsstatus und Wetter fest.

## Gut zu wissen
- Kostet nichts. Ein Lauf braucht ca. 3 Minuten, das Gratis-Kontingent liegt bei 2.000 Minuten im Monat.
- Läuft im Repo 60 Tage lang nichts Neues, pausiert GitHub den Sonntags-Zeitplan. Der Button funktioniert trotzdem. Zum Reaktivieren unter **Actions** auf „Enable workflow“ tippen.
- Der Token läuft nach einem Jahr ab. Dann Schritt 3 wiederholen.
- Die Seite ist unter der Adresse öffentlich erreichbar. Sie zeigt nur NFL-Daten, nichts Persönliches.
