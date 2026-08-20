# Metoda BMT (BEMT) — analityczne obliczenia śmigła

## Opis metody

Metoda elementu łopatkowego sprzężona z teorią pędu (BEMT, ang. *Blade Element Momentum Theory*)
łączy analizę sił aerodynamicznych działających na lokalne elementy łopaty z bilansem pędu
strugi przepływającej przez tarczę śmigła. W praktyce łopa dzieli się na pierścieniowe elementy,
a dla każdego z nich — z wykorzystaniem geometrii łopaty i charakterystyk profilu — wyznacza się
lokalne siły aerodynamiczne oraz wymuszone zmiany prędkości indukowanej. Po osiągnięciu zbieżności
iteracyjnej sumuje się wkłady wszystkich elementów, otrzymując globalny ciąg `T`, moment `Q`,
moc `P` i sprawność `eta` w funkcji prędkości lotu.

Metoda ta pozwala w krótkim czasie oszacować rząd wielkości sił i mocy wytwarzanych przez śmigło,
dzięki czemu stanowi szybką, referencyjną weryfikację symulacji CFD.

## Zawartość folderu

| Plik / folder | Opis |
|---|---|
| `bemt_propeller.py` | Skrypt Python realizujący obliczenia BEMT dla śmigła dwułopatowego |
| `profile/` | Charakterystyki aerodynamiczne profili NACA 44xx dla danych liczb Reynoldsa (pliki `.dat.txt`) |
| `V_0/` … `V_30/` | Wyniki obliczeń dla prędkości lotu 0–30 m/s: rozkłady ciągu, momentu i współczynników indukcji + pliki `.txt` |
| `wykresy_wynikow/` | Zbiorcze wykresy rozkładów ciągu, momentu i współczynników indukcji |
| `podsumowanie_wynikow.png` / `.txt` | Zbiorcze charakterystyki śmigła (ciąg, moc, sprawność) |
| `porownanie_a.png`, `porownanie_dT.png`, `porownanie_dQ.png` | Porównanie rozkładów indukcji `a`, ciągu `dT` i momentu `dQ` wzdłuż promienia |

## Geometria śmigła

- promień łopaty: `R = 0.25 m`, średnica `0.5 m`
- liczba łopat: `B = 2`
- stacje promieniowe (r/R): 0.20, 0.35, 0.50, 0.65, 0.80, 0.95, 1.00
- profile: NACA4415, NACA4412, NACA4412, NACA4410, NACA4409, NACA4408, NACA4408

## Warunki pracy

- prędkość obrotowa: `3000 rpm` (`omega = 300 rad/s`)
- prędkości lotu: `V = 0, 5, 10, 15, 20, 25, 30 m/s`
- gęstość powietrza: `rho = 1.225 kg/m3`
- lepkość dynamiczna: `mu = 1.81e-5 Pa·s`

## Uruchomienie

```bash
python bemt_propeller.py
```

Skrypt generuje wykresy rozkładów lokalnych parametrów oraz zapisuje podsumowanie
wyników do plików `wyniki_V_*.txt` i wykresów PNG.