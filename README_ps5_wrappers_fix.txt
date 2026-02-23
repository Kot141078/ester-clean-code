PS5 Wrappers Fix — chto izmenilos
- Ispravleny .ps1: teper NE ispolzuyut stroku 'py -3' kak odin ispolnyaemyy obekt i rabotayut kak s 'py', tak i s 'python'.
- Ubrany ternarnye operatory, nesovmestimye s PS5.
- Dobavlen data/app/extra_routes.sample.json dlya ruchnoy zapisi pri neobkhodimosti.

Shagi:
1) tools\add_extra_routes.bat
2) scripts\env_sanitize.bat
3) scripts\gen_owner_jwt.bat
4) py -3 app.py (ili python app.py)

Esli BAT ne podkhodit — mozhno rukami sozdat data\app\extra_routes.json, vzyav soderzhimoe iz data\app\extra_routes.sample.json.

c=a+b
