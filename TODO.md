# TODO

## Bieżąca wersja — końcowa weryfikacja

- Zakres implementacji bieżącej wersji jest zamknięty.
- Test na Oracle zaplanowany na 10 listopada 2026: aktualizacja wyników w paczkach i licznik pominiętych obiektów. Działanie paczek poza Oracle zostało potwierdzone przez użytkownika.

## Następna wersja

- Przejść treść pomocy oraz jej budowanie i dołączanie do paczki.
- Dodać obsługę warstw pamięciowych przez kopiowanie ID i geometrii w głównym wątku przed uruchomieniem analizy w tle. Zachować oryginalne ID do zaznaczania wyników. Przy tej zmianie rozważyć uwzględnianie niezapisanych edycji.

## Zaimplementowane

- Aktualizacja wyników po zebraniu co najmniej 100 obiektów, z zachowaniem pełnych kroków przeszukiwania i wysłaniem pozostałej paczki na końcu. Użytkownik potwierdził działanie poza Oracle.
- Usunięcie procentowego postępu i dodanie licznika unikalnych obiektów pominiętych z powodu nieobsługiwanej lub pustej geometrii.
- Poprawki uwag walidatora: porównania do True, nazwa zmiennej l, zawężenie bare except oraz usunięcie nieużywanych helperów Qt.
- Polskie tłumaczenie i18n/pl.ts ze wszystkimi wpisami zatwierdzonymi, plik pl.qm oraz konfiguracja dołączania i18n do paczki. Użytkownik potwierdził działanie tłumaczenia w QGIS.
- Ładowanie tłumacza przed przygotowaniem prefiksów liczników.
- Aktualizacja zbierania tekstów do PyQt5/PyQt6: scripts/update_strings.py oraz wejście Bash scripts/update-strings.sh.
- Skrypt scripts/linguist.bat do otwierania polskiego tłumaczenia w środowisku QGIS.
