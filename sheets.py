import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from config import SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Sana",
    "Ism",
    "Telefon",
    "Viloyat",
    "Bo'lim",
    "Savol",
    "Til",
    "Telegram ID",
    "Username",
    "Telegram ismi",
    "Status",
]

_client: gspread.Client | None = None
_sheet: gspread.Worksheet | None = None


def _get_sheet() -> gspread.Worksheet:
    """Worksheet ga ulanish (bir marta ochiladi)."""
    global _client, _sheet
    if _sheet is not None:
        return _sheet

    # Railway (yoki boshqa server): env var dan o'qiydi
    # Lokal: credentials.json fayldan o'qiydi
    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        creds_info = json.loads(creds_env)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
    _client = gspread.authorize(creds)
    spreadsheet = _client.open_by_key(SHEET_ID)

    # "Murojaatlar" nomli varaq bor bo'lsa ochadi, yo'q bo'lsa yaratadi
    try:
        _sheet = spreadsheet.worksheet("Murojaatlar")
    except gspread.WorksheetNotFound:
        _sheet = spreadsheet.add_worksheet(
            title="Murojaatlar", rows=1000, cols=len(HEADERS)
        )
        _sheet.append_row(HEADERS)
        # Sarlavhalarni qalin va ranggi qilish
        _sheet.format("A1:K1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.86},
        })

    return _sheet


def save_to_sheet(
    name: str,
    phone: str,
    region: str,
    category: str,
    question: str,
    lang: str,
    telegram_id: int,
    username: str,
    fullname: str,
    status: str = "active",
) -> bool:
    """Foydalanuvchi ma'lumotlarini Google Sheets ga saqlaydi."""
    try:
        sheet = _get_sheet()
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            name,
            phone,
            region,
            category,
            question,
            "O'zbek" if lang == "uz" else "Русский",
            str(telegram_id),
            username,
            fullname,
            "Aktiv" if status == "active" else "Deaktiv",
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Google Sheets xatosi: {e}")
        return False


def update_status_in_sheet(telegram_id: int, new_status: str) -> None:
    """Foydalanuvchi statusini Sheets da yangilaydi."""
    try:
        sheet = _get_sheet()
        # Telegram ID ustuni (8-ustun, H)
        cell_list = sheet.col_values(8)
        for i, cell in enumerate(cell_list):
            if cell == str(telegram_id):
                # Status ustuni (11-ustun, K)
                sheet.update_cell(
                    i + 1, 11,
                    "Aktiv" if new_status == "active" else "Deaktiv"
                )
    except Exception as e:
        print(f"Status yangilashda xato: {e}")
