"""Поставщики курсов валют."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests

from app.exceptions import NotFoundError, ProviderError
from app.models import Rate


class RateProvider(ABC):
    """Абстрактный поставщик курсов: общий интерфейс для всех реализаций."""

    @abstractmethod
    def get_rates(self) -> dict[str, Rate]:
        """Вернуть словарь {код валюты: Rate}."""

    def get_rate(self, code: str) -> Rate:
        """Общий для всех наследников метод на основе get_rates()."""
        rates = self.get_rates()
        code = code.strip().upper()
        if code not in rates:
            raise NotFoundError(f"Курс {code} не найден")
        return rates[code]


class CbrXmlProvider(RateProvider):
    """Курсы ЦБ РФ из XML."""

    URL = "https://www.cbr.ru/scripts/XML_daily.asp"
    TIMEOUT = 10
    HEADERS = {"User-Agent": "Mozilla/5.0 (student lab: currency tracker)"}

    def __init__(self, url: str | None = None, timeout: float | None = None) -> None:
        self._url = url or self.URL
        self._timeout = timeout or self.TIMEOUT
        self._skipped_count = 0

    @property
    def skipped_count(self) -> int:
        """Количество пропущенных повреждённых записей при последнем разборе."""
        return self._skipped_count

    def get_rates(self) -> dict[str, Rate]:
        try:
            response = requests.get(self._url, headers=self.HEADERS, timeout=self._timeout)
            response.raise_for_status()
        except requests.Timeout as exc:
            # Специфичное исключение должно идти ПЕРВЫМ
            raise ProviderError(f"Сервер ЦБ РФ не ответил за {self._timeout} секунд") from exc
        except requests.RequestException as exc:
            # Общее исключение для всех остальных сетевых проблем
            raise ProviderError(f"Не удалось получить данные ЦБ РФ: {exc}") from exc
        
        return self.parse(response.content)

    def parse(self, xml_data: bytes) -> dict[str, Rate]:
        """Разобрать XML ЦБ РФ. Кодировку windows-1251 парсер определит сам."""
        try:
            root = ET.fromstring(xml_data)
            on_date = datetime.strptime(root.attrib["Date"], "%d.%m.%Y").date()
        except (ET.ParseError, KeyError, ValueError) as exc:
            raise ProviderError(f"Некорректный ответ ЦБ РФ: {exc}") from exc

        rates: dict[str, Rate] = {}
        self._skipped_count = 0  # Сбрасываем счетчик перед новым разбором
        
        for valute in root.findall("Valute"):
            try:
                code = valute.findtext("CharCode", "").strip()
                name = valute.findtext("Name", "").strip()
                nominal = int(valute.findtext("Nominal", "").strip())
                value = Decimal(valute.findtext("Value", "").strip().replace(",", "."))
                
                num_code_raw = valute.findtext("NumCode", "").strip()
                num_code = num_code_raw if num_code_raw else None
                
                rates[code] = Rate(code, name, nominal, value, on_date, num_code)
            except (ValueError, InvalidOperation):
                self._skipped_count += 1
                continue  # пропускаем повреждённую запись
                
        return rates


class StaticRateProvider(RateProvider):
    """Курсы из заранее заданного списка."""

    def __init__(self, rates: Iterable[Rate]) -> None:
        self._rates = {rate.code: rate for rate in rates}

    def get_rates(self) -> dict[str, Rate]:
        return dict(self._rates)   # копия: снаружи нельзя испортить внутренний словарь

    @classmethod
    def demo(cls) -> StaticRateProvider:
        """Демонстрационный набор. Значения условные."""
        today = date.today()
        return cls([
            Rate("USD", "Доллар США", 1, Decimal("80.0000"), today, "840"),
            Rate("EUR", "Евро", 1, Decimal("93.0000"), today, "978"),
            Rate("CNY", "Китайский юань", 1, Decimal("11.2000"), today, "156"),
            Rate("JPY", "Японских иен", 100, Decimal("53.0000"), today, "392"),
        ])