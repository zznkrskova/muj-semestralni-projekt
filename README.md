# Plánovač aktivit (PySide6)

Desktopová aplikace pro plánování denních aktivit s podporou **opakování**, **šablon**, **poznámek**, **drag & drop** a **doporučení** podle denní fyzické/psychické zátěže.
Aplikace využívá **SQLite** (soubor `planner.db`) a GUI nad **PySide6/Qt**.

---

## 📦 Požadavky

- **Python** 3.8+ (doporučeno 3.10–3.12)
- **pip**
- **PySide6** (instaluje se přes `requirements.txt`)

---

## 🔧 Instalace

Doporučený postup na čistém systému:

```bash
# 1) vytvoření a aktivace virtuálního prostředí (není nutné)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

# 2) databázi možno otevřít přímo v pythonu pomocí
sqlite3  nebo použít externí aplikaci

# 3) instalace závislostí
pip install -r requirements.txt
```

Po instalaci je možné aplikaci spustit přímo (viz níže).
> První spuštění zobrazí průvodce nastavením **cílové fyzické/psychické zátěže**, hodnoty se ukládají do tabulky `flags`.

---

## ▶️ Spuštění

```bash
python main.py
```

Vstupní modul `main.py` nejprve **vytvoří/aktualizuje DB schéma** (`create_tables()`), poté otevře hlavní okno `MainWindow`.

---

## 🗂 Struktura projektu

```
.
├─ main.py              # vstupní bod aplikace (spuštění GUI, init DB)
├─ database.py          # SQLite schéma a CRUD (viz níže)
├─ logic.py             # výpočty, konflikty, formátování, doporučení
├─ gui_main.py          # hlavní okno, kalendář, render aktivit, drag&drop
├─ gui_dialogs.py       # dialogy: přidání/úpravy, vícedenní, výběr dnů, poznámky
├─ gui_widgets.py       # ActivityWidget (bublina aktivity, barvy dle obtížnosti)
├─ gui_base.py          # sdílené prvky dialogů (šablony, čas, obtížnost, odpoč.)
├─ requirements.txt
├─ README.md
└─ (lokalni/generovane) .venv/, venv/, .vscode/, planner.db
```

---

## ✨ Hlavní funkce

### Aktivity
- **Jednorázové**: pevné datum (`activities.date`).
- **Dlouhodobé (opakované)**: řízené kombinací `recurring=1` + `recurring_days` (**Mon–Sun**) nebo `recurring_date` (**MM-DD**, např. výročí). Výjimky se ukládají do `activity_exceptions` a jednotlivé dny lze vyjmout/„skrýt“.

### Konflikty a řešení kolizí
Při přidání/posunu kolidující aktivity nabídne dialog volby: **nahradit**, **ponechat překryv**, **posunout novou** (vyhledání prvního volného slotu), nebo **zrušit**. Podporováno i v hromadném módu „na více dní“.

### Drag & drop v kalendáři
Aktivitu lze přetáhnout na jiné datum v kalendáři; pro dlouhodobou aktivitu se při přesunu vytvoří **výjimka** v původní sérii a vloží se **jednorázová kopie** v cílovém dni.

### Šablony aktivit
- Výběr šablony v dialozích + **automatické vytvoření šablony** z nové aktivity, pokud zatím neexistuje (podle jména).
- Šablony uchovávají i příznak **celodenní** a **typ zátěže** (mental/physical).

### Poznámky
- Ke každé aktivitě lze přidat poznámku **pro konkrétní den** (`activity_notes`). Zobrazuje se přímo v bublině aktivity s ikonou 📝.

### Doporučení dne
- Výpočet **fyzické** a **psychické** zátěže dle všech aktivit dne (zohledňuje dobu trvání × náročnost ± odpočinek).
- Porovnání s **cílovými rozmezími** (min/max) a barevné zvýraznění panelu doporučení.

### Odpočinek (rest)
- Aktivita může být odpočinková: `is_rest=1`, `rest_type` = "physical"/"mental", `rest_amount` = 1–5.
- **Odpočinek zátěž odečítá** (jen v dané složce zátěže).

---

## 🧭 Uživatelské scénáře (rychlé tutoriály)

### 1) Přidání jednorázové aktivity
1. Menu → **„+ Přidat jednorázovou aktivitu“**  
2. Vyplň **název**, **kategorii**, **čas** (nebo „Celodenní“), **obtížnost (1–5)**, volitelně **odpočinek**  
3. Vyber **datum** a potvrď  
4. Pokud dojde ke konfliktu, zvol řešení v dialogu

### 2) Dlouhodobá aktivita (opakovaní dny v týdnu / roční)
1. Menu → **„+ Přidat dlouhodobou aktivitu“**  
2. Zaškrtni dny (Po–Ne) **nebo** aktivuj **„Opakovat každý rok“** a vyber **MM‑DD**  
3. Potvrď (případné konflikty řeš stejně jako výše)

### 3) Vložit aktivitu na více dní
1. Menu → **„+ Přidat aktivitu na více dní“**  
2. Vyber **rozsah dat**; filtruj **pracovní dny**/**víkendy**  
3. Při konfliktech může aplikace **najít nejbližší volný slot** (globální volba pro dávku)

### 4) Poznámka k aktivitě
- Pravé tlačítko na bublině aktivity → **„Přidat/upravit poznámku“** (uloží se pro vybraný den)

---

## 🧱 Architektura & datový model

### Moduly
- **`database.py`** – schéma tabulek, CRUD, helpery `_fetch_*`, `_execute`. Obsahuje tabulky:  
  `activities`, `activity_templates`, `flags`, `activity_notes`, `activity_exceptions`
- **`logic.py`** – čistá logika: výpočet denní zátěže, formát času, vyhledání konfliktů a prvního volného slotu, doporučení dne.
- **`gui_*`** – prezentační vrstva (hlavní okno, widget aktivity, dialogy), obsluha drag&drop a workflow.

### Klíčová pole tabulek (výběr)
- `activities`:  
  `id, name, category, start_hour, start_minute, end_hour, end_minute, difficulty, date, recurring, recurring_days, recurring_date, all_day, load_type, is_rest, rest_type, rest_amount`
- `activity_templates`:  
  `id, name, category, start_hour, start_minute, end_hour, end_minute, difficulty, all_day, load_type, is_rest, rest_type, rest_amount`

> **Celodenní aktivita** je reprezentována časy **00:00–23:59** a/nebo příznakem `all_day`.

---

## 🧮 Výpočet zátěže & doporučení

- Zátěž = **(délka v hodinách) × (obtížnost 1–5)**, sčítá se zvlášť pro **fyzickou** a **psychickou** složku podle `load_type`.  
- **Odpočinek** (`is_rest=1`) **zátěž odečítá** podle `rest_type` a `rest_amount`.  
- Cílové rozsahy (min/max) se berou z `flags` a lze je kdykoli změnit v menu **„Nastavení cílových zátěží“**.  
- Panel doporučení ve hlavním okně zobrazuje slovní stav i **barevné zvýraznění** (zvýšit aktivitu / doporučený odpočinek / vyváženo).

---

## ⌨️ Klávesové a UX tipy

- **Klik levým**: vybere aktivitu (zvýraznění rámečkem).  
- **Klik pravým**: kontextové menu (Upravit, Přidat/Upravit poznámku, Smazat).  
- **Přetažení**: chyť bublinu myší a pusť na jiný den v kalendáři — otevře se řešení konfliktů a aktivita se přesune.

---

## 🧪 Testování (manuální sanity-check)

1. Spusť aplikaci → dokonči první nastavení cílů zátěže.  
2. Přidej jednorázovou aktivitu 09:00–10:00, obtížnost 3.  
3. Přidej na stejné datum druhou aktivitu 09:30–10:30 → očekávej dialog konfliktů.  
4. Zkus přetáhnout aktivitu na jiný den v kalendáři → zkontroluj změnu data a případnou výjimku u série.  
5. Přidej poznámku k aktivitě → ikona 📝 je viditelná.  
6. Otevři „Nastavení cílových zátěží“, změň limity, ověř změnu panelu doporučení.

---

**Poslední aktualizace:** Únor 2026
