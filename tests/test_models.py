import pytest

from decimal import Decimal
from datetime import date
from app.exceptions import AppError, ValidationError
from app.models import BaseEntity, Currency, Subscription, User, Rate


def test_user_created_with_attributes():
    user = User("ivan", "Ivan@Example.com")
    assert user.username == "ivan"
    assert user.email == "ivan@example.com"  # email приводится к нижнему регистру
    assert user.id == 1


def test_ids_are_sequential_per_class():
    first, second = User("anna", "a@ex.ru"), User("boris", "b@ex.ru")
    currency = Currency("USD", "Доллар США")
    assert (first.id, second.id) == (1, 2)
    assert currency.id == 1  # у Currency свой счётчик


def test_class_attribute_shared_by_instances():
    a, b = User("anna", "a@ex.ru"), User("boris", "b@ex.ru")
    assert a.USERNAME_MIN_LENGTH == b.USERNAME_MIN_LENGTH == User.USERNAME_MIN_LENGTH


@pytest.mark.parametrize("bad", ["", "  ", "ab", "имя", "with space", "x" * 33, None])
def test_invalid_username(bad):
    with pytest.raises(ValidationError):
        User(bad, "a@ex.ru")


@pytest.mark.parametrize("bad", ["", "no-at.ru", "a@b", "a b@ex.ru"])
def test_invalid_email(bad):
    with pytest.raises(ValidationError):
        User("anna", bad)


def test_setter_validates_on_change():
    user = User("anna", "a@ex.ru")
    with pytest.raises(ValidationError):
        user.username = "x"
    assert user.username == "anna"  # старое значение сохранилось


def test_id_is_read_only():
    user = User("anna", "a@ex.ru")
    with pytest.raises(AttributeError):
        user.id = 100


def test_private_attribute_name_mangling():
    user = User("anna", "a@ex.ru")
    assert not hasattr(user, "__id")
    assert user._BaseEntity__id == user.id


@pytest.mark.parametrize("code, expected", [("usd", "USD"), (" eur ", "EUR")])
def test_currency_code_normalized(code, expected):
    assert Currency(code, "Валюта").code == expected


@pytest.mark.parametrize("bad", ["US", "USDT", "12A", "ДОЛ", ""])
def test_invalid_currency_code(bad):
    with pytest.raises(ValidationError):
        Currency(bad, "Валюта")


def test_inheritance():
    user = User("anna", "a@ex.ru")
    assert isinstance(user, BaseEntity)
    assert issubclass(Currency, BaseEntity)
    assert issubclass(ValidationError, AppError)


def test_to_dict_extends_parent():
    data = User("anna", "a@ex.ru").to_dict()
    assert {"id", "created_at", "username", "email"} <= data.keys()


def test_entities_equal_by_class_and_id():
    user = User("anna", "a@ex.ru")
    currency = Currency("USD", "Доллар США")
    assert user.id == currency.id == 1
    assert user != currency


def test_str_and_repr():
    user = User("anna", "a@ex.ru")
    assert str(user) == "anna <a@ex.ru>"
    assert repr(user) == "User(id=1, username='anna')"


def test_subscriptions_with_same_pair_are_equal():
    user, currency = User("anna", "a@ex.ru"), Currency("USD", "Доллар США")
    assert Subscription(user, currency) == Subscription(user, currency)
    assert len({Subscription(user, currency), Subscription(user, currency)}) == 1


def test_subscription_requires_objects():
    with pytest.raises(TypeError):
        Subscription("anna", "USD")


### Задание 4
@pytest.mark.parametrize("invalid_name", [
    "А",                  # Слишком короткое (1 символ)
    "  А  ",              # Слишком короткое после strip
    "Анна123",            # Содержит цифры
    "Анна!",              # Содержит спецсимвол
    "А" * 101,            # Слишком длинное (101 символ)
])
def test_user_invalid_full_name(invalid_name):
    with pytest.raises(ValidationError):
        User("anna", "a@ex.ru", full_name=invalid_name)


def test_user_valid_full_name():
    user = User("anna", "a@ex.ru", full_name="  Анна-Мария  ")
    assert user.full_name == "Анна-Мария"  # Пробелы обрезаны


# 2. is_active только для чтения
def test_user_is_active_read_only():
    user = User("anna", "a@ex.ru")
    assert user.is_active is True
    
    with pytest.raises(AttributeError):
        user.is_active = False  # Нельзя изменить напрямую
    
    user.deactivate()
    assert user.is_active is False


# 3. Сортировка курсов (по стоимости одной единицы)
def test_rate_sorting():
    today = date.today()
    usd = Rate("USD", "Доллар", 1, Decimal("90.0"), today)
    jpy = Rate("JPY", "Йена", 100, Decimal("50.0"), today) # 50 руб за 100 шт = 0.5 за 1 шт
    
    rates = [jpy, usd]
    sorted_rates = sorted(rates, reverse=True)
    
    # Доллар должен быть первым, так как 90 > 0.5
    assert sorted_rates[0].code == "USD"
    assert sorted_rates[1].code == "JPY"