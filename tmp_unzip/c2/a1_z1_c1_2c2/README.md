# New Simple Crypto Bot 🦾

Acesta este codul sursă optimizat pentru bot-ul tău de vânzări. Include sistemul de Sectoare pentru București, livrare automată cu 3 confirmări și Panou Admin complet.

## 🚀 Instalare Rapidă

1. **Cerințe sistem**: 
   - Instalează [Python 3.12+](https://www.python.org/)
   - Instalează dependințele: `pip install -r requirements.txt`

2. **Configurare (.env)**:
   - Deschide fișierul `.env` și completează:
     - `BOT_TOKEN`: Token-ul tău de la @BotFather
     - `ADMIN_IDS`: ID-ul tău de Telegram (ex: `12345678`)
     - `TATUM_API_KEY`: Cheia ta API de la Tatum pentru verificări blockchain.
     - `LTC_ADDRESSES`: Cele 5 adrese LTC (separate prin virgulă).

3. **Pornire**:
   - Rulează bot-ul: `python bot.py`

## 📂 Structura Fișierelor
- `bot.py`: Nucleul aplicației.
- `handlers/`: Logica pentru Utilizatori și Admini.
- `assets/`: Imaginile pentru Categorii și Orașe.
- `database.py`: Schema bazei de date.
- `utils/`: Utilitare pentru preț LTC, QR codes și Tatum API.

## 👮 Admin Panel
- Trimite comanda `/admin` în bot pentru a gestiona totul.
- Trimite comanda `/pending` pentru a vedea vânzările active.

## ⚠️ Note Importante
- **Auto-Setup**: La prima pornire, bot-ul detectează dacă baza de date este goală și configurează automat orașele (București + Craiova) și categoriile (❄️, 🐎, etc.).
- **Branding GTA**: Bot-ul folosește fontul `gta.ttf` pentru a scrie automat numele orașelor și sectoarelor pe imagini, cu stil transparent premium.
- **Suport Video**: Adminii pot adăuga atât POZE cât și VIDEO în stoc.
- **Imagini Spoiler**: Sunt mapate automat la fișierele `SECRET_*.jpg` din `/assets`.
- **Precomenzi**: Utilizatorii sunt limitați la o singură precomandă activă simultan.

---
© 2026 New Simple Crypto Bot. Toate drepturile rezervate.
