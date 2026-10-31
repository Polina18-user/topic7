"""Сервисный слой: регистрация пользователей и управление подписками."""


from __future__ import annotations

from app.exceptions import DuplicateError, NotFoundError, InactiveUserError
from app.models import Currency, Rate, Subscription, User
from app.providers import RateProvider
from datetime import datetime

import json
from pathlib import Path


class CurrencyTracker:
    """Хранит пользователей, валюты и подписки в памяти."""

    def __init__(self, provider: RateProvider) -> None:
        self._provider = provider                       # внедрение зависимости
        self._users: dict[int, User] = {}
        self._currencies: dict[str, Currency] = {}      # ключ — код валюты
        self._subscriptions: set[Subscription] = set()

    # ---------- пользователи ----------
    def register_user(self, username: str, email: str) -> User:
        user = User(username, email)      # сначала проверка данных в модели
        for existing in self._users.values():
            if existing.username.lower() == user.username.lower():
                raise DuplicateError(f"Имя {user.username!r} уже занято")
            if existing.email == user.email:
                raise DuplicateError(f"Email {user.email!r} уже зарегистрирован")
        self._users[user.id] = user
        return user

    def get_user(self, user_id: int) -> User:
        try:
            return self._users[user_id]
        except KeyError:
            raise NotFoundError(f"Пользователь с id={user_id} не найден") from None

    @property
    def users(self) -> list[User]:
        return list(self._users.values())

    # ---------- валюты ----------
    def sync_currencies(self) -> int:
        added = 0
        for code, rate in self._provider.get_rates().items():
            if code in self._currencies:
                # Обновляем данные у существующей валюты
                self._currencies[code].name = rate.name
                self._currencies[code].num_code = rate.num_code
            else:
                # Создаём новую с передачей num_code
                self._currencies[code] = Currency(code, rate.name, rate.num_code)
                added += 1
        return added

    def get_currency(self, code: str) -> Currency:
        code = code.strip().upper()
        try:
            return self._currencies[code]
        except KeyError:
            raise NotFoundError(f"Валюта с кодом {code!r} не найдена") from None

    @property
    def currencies(self) -> list[Currency]:
        return sorted(self._currencies.values(), key=lambda c: c.code)

    # ---------- подписки ----------
    def subscribe(self, user_id: int, code: str) -> Subscription:
        user = self.get_user(user_id)
        
        if not user.is_active:
            raise InactiveUserError(f"Пользователь {user.username!r} деактивирован")
        subscription = Subscription(self.get_user(user_id), self.get_currency(code))
        if subscription in self._subscriptions:
            raise DuplicateError("Подписка уже существует")
        self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, user_id: int, code: str) -> None:
        user = self.get_user(user_id)
        currency = self.get_currency(code)
        
        # Создаем «временный» объект, чтобы воспользоваться его __eq__ и __hash__
        target = Subscription(user, currency)
        try:
            self._subscriptions.remove(target)
        except KeyError:
            raise NotFoundError(
                f"Подписка пользователя id={user_id} на {currency.code} не найдена"
            ) from None

    def get_user_currencies(self, user_id: int) -> list[Currency]:
        user = self.get_user(user_id)
        found = [s.currency for s in self._subscriptions if s.user == user]
        return sorted(found, key=lambda c: c.code)

    def get_subscribers(self, code: str) -> list[User]:
        currency = self.get_currency(code)
        found = [s.user for s in self._subscriptions if s.currency == currency]
        return sorted(found, key=lambda u: u.id)

    def get_user_rates(self, user_id: int) -> list[Rate]:
        rates = self._provider.get_rates()
        return [rates[c.code] for c in self.get_user_currencies(user_id) if c.code in rates]

    def save(self, path: str | Path) -> None:
        """Сохранить состояние трекера в JSON-файл."""
        data = {
            "users": [user.to_dict() for user in self._users.values()],
            "currencies": [currency.to_dict() for currency in self._currencies.values()],
            "subscriptions": [
                {"user_id": sub.user.id, "currency_id": sub.currency.id}
                for sub in self._subscriptions
            ],
        }
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str | Path) -> None:
        """Восстановить состояние трекера из JSON-файла."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Файл данных не найден: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Очищаем текущее состояние
        self._users.clear()
        self._currencies.clear()
        self._subscriptions.clear()

        # 1. Восстанавливаем пользователей
        for u_data in data.get("users", []):
            user = User.__new__(User)  # Создаем пустой объект, минуя __init__
            # Восстанавливаем базовые поля (id, created_at) в обход property
            object.__setattr__(user, "_BaseEntity__id", u_data["id"])
            object.__setattr__(user, "_created_at", datetime.fromisoformat(u_data["created_at"]))
            
            # Восстанавливаем поля User через сеттеры (с валидацией)
            user.username = u_data["username"]
            user.email = u_data["email"]
            user.full_name = u_data.get("full_name")
            user._is_active = u_data.get("is_active", True)
            
            self._users[user.id] = user

        # Синхронизируем счётчик ID пользователей, чтобы новые не получили старые номера
        if self._users:
            User._id_counter = max(self._users.keys())

        # 2. Восстанавливаем валюты
        for c_data in data.get("currencies", []):
            currency = Currency.__new__(Currency)
            object.__setattr__(currency, "_BaseEntity__id", c_data["id"])
            object.__setattr__(currency, "_created_at", datetime.fromisoformat(c_data["created_at"]))
            
            currency.code = c_data["code"]
            currency.name = c_data["name"]
            currency.num_code = c_data.get("num_code")
            
            self._currencies[currency.code] = currency

        # Синхронизируем счётчик ID валют
        if self._currencies:
            Currency._id_counter = max(c.id for c in self._currencies.values())

        # 3. Восстанавливаем подписки
        for s_data in data.get("subscriptions", []):
            user = self._users.get(s_data["user_id"])
            # Ищем валюту по ID
            currency = next((c for c in self._currencies.values() if c.id == s_data["currency_id"]), None)
            
            if user and currency:
                sub = Subscription(user, currency)
                self._subscriptions.add(sub)