# TODO

## Uwagi po testach w Oracle

- Aktualizować wyniki analizy i zaznaczenie w paczkach po 100–200 obiektów, aby ograniczyć częstotliwość aktualizacji interfejsu. Dokładny rozmiar paczki dobrać podczas testów.
- Usunąć procentowy postęp z interfejsu: obecnie nie ma wiarygodnego sposobu określenia, ile obiektów pozostało do przeanalizowania.
- W miejscu procentowego postępu wyświetlać liczbę pominiętych obiektów. Przed implementacją ustalić, jakie przyczyny pominięcia obejmuje licznik.

## Pozostałe ustalenia

- Przygotować tłumaczenia wtyczki.
- Przejść treść pomocy oraz jej budowanie i dołączanie do paczki.
- Dodać obsługę warstw pamięciowych przez kopiowanie ID i geometrii w głównym wątku przed uruchomieniem analizy w tle. Zachować oryginalne ID do zaznaczania wyników. Przy tej zmianie rozważyć uwzględnianie niezapisanych edycji.
