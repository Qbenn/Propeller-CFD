# Propeller CFD — Analiza aerodynamiczna śmigła metodą BEMT i CFD

## Opis projektu

Projekt obejmuje analizę aerodynamiczną dwułopatowego śmigła o średnicy 0.5 m
przy stałej prędkości obrotowej 3000 rpm.

- **Metoda BEMT (BMT)** — szybkie, analityczne oszacowanie ciągu, momentu, mocy
  i sprawności dla prędkości lotu 0–30 m/s (folder `bmt/`).
- **CFD (ANSYS Fluent)** — symulacje numeryczne metodą MRF z modelem turbulencji
  k-omega SST służące jako weryfikacja wyników analitycznych (folder `raport/`).

## Struktura repozytorium

```
Propeller CFD/
├── bmt/          # Metoda BEMT: kod Python, dane profili NACA, wyniki i wykresy
├── model/        # Modele geometrii śmigła (pliki .prt, Siemens NX) dla stacji promieniowych
├── raport/       # Raport naukowy (LaTeX) z opisem metodyki i wynikami
└── README.md
```

## Zawartość poszczególnych folderów

### `model/`
Modele CAD łopat śmigła w programie Siemens NX (pliki `.prt`) dla kolejnych
stacji promieniowych (r/R = 0.20–1.00) oraz model bazowy `model1.prt`.

### `bmt/`
- `bemt_propeller.py` — skrypt obliczeniowy metody BEMT,
- `profile/` — charakterystyki profili NACA 44xx,
- `V_0/` … `V_30/` — wyniki dla poszczególnych prędkości lotu,
- szczegóły: zobacz `bmt/README.md`.

### `raport/`
- `main.tex` — główny plik raportu w LaTeX,
- `main.pdf` — skompilowany raport,
- `wykresy/` — zbiorcze charakterystyki CFD (wyniki symulacji),
- `wykresy_smigla/` — rozkłady prędkości i ciśnień wokół śmigła dla danych prędkości,
- pozostałe obrazy (siatka, geometria, monitory solvera).

## Wymagania

- Python 3 + NumPy, SciPy, Matplotlib (dla `bmt/bemt_propeller.py`)
- TeX Live / MiKTeX (dla kompilacji `raport/main.tex`)
- ANSYS Fluent (dla powtórzenia symulacji CFD)

## Licencja

Materiały do użytku edukacyjnego / pracy inżynierskiej. Nie są przeznaczone
do celów komercyjnych bez zgody autora.