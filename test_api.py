import pytest
from fastapi.testclient import TestClient
import main  # Импортируем сам модуль main для подмены функций
from main import app

client = TestClient(app)

# Автоматически отключает реальную отправку сообщений в Telegram при тестах
@pytest.fixture(autouse=True)
def mock_tg(monkeypatch):
    async def fake_send(*args, **kwargs):
        return None
    monkeypatch.setattr(main, "send_tg_notification", fake_send)

# Наши тест-кейсы
test_cases = [
    ("№№№№№№№", "+7 (777) 123-45-6", 200, "Валидный заказ Erzman"),
    ("Alex", "87071234567", 200, "Валидный заказ без спецсимволов"),
    ("Иван", "123", 400, "Слишком короткий телефон"),
    ("Иван", "not-a-number!!", 400, "Телефон содержит буквы"),
    ("Я", "+77771234567", 400, "Слишком короткое имя (1 символ)"),
    ("ОченьДлинноеИмяКотороеНеПройдетВалидациюПоДлине", "+77771234567", 400, "Слишком длинное имя"),
]

# Красивые системные имена для каждого теста вместо юникода
test_ids = [
    "valid_order_erzman",
    "valid_order_clean_phone",
    "invalid_short_phone",
    "invalid_phone_with_letters",
    "invalid_short_username",
    "invalid_long_username"
]

# Передаем параметры правильно
@pytest.mark.parametrize("username, phone, expected_status, description", test_cases, ids=test_ids)
def test_submit_order_security(username, phone, expected_status, description):
    response = client.post(
        "/submit-order",
        data={
            "item_name": "Erzman",
            "username": username,
            "phone": phone,
            "email": "test@example.com"
        }
    )
    assert response.status_code == expected_status, \
        f"Тест '{description}' провален! Ждали {expected_status}, но получили {response.status_code}. Ответ: {response.text}"