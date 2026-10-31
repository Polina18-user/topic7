"""Тесты для провайдеров курсов валют."""
from decimal import Decimal

import pytest
import requests

from app.exceptions import NotFoundError, ProviderError
from app.providers import CbrXmlProvider, RateProvider, StaticRateProvider


SAMPLE_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="27.10.2026" name="Foreign Currency Market">
<Valute ID="R01235"><NumCode>840</NumCode><CharCode>USD</CharCode><Nominal>1</Nominal>
<Name>Доллар США</Name><Value>80,5000</Value></Valute>
<Valute ID="R01820"><NumCode>392</NumCode><CharCode>JPY</CharCode><Nominal>100</Nominal>
<Name>Японских иен</Name><Value>53,0000</Value></Valute>
</ValCurs>""".encode("windows-1251")


def test_abstract_provider_cannot_be_created():
    with pytest.raises(TypeError):
        RateProvider()


def test_cbr_parse():
    rates = CbrXmlProvider().parse(SAMPLE_XML)
    assert set(rates) == {"USD", "JPY"}
    assert rates["USD"].name == "Доллар США"
    assert rates["JPY"].per_unit == Decimal("0.53")


def test_cbr_parse_broken_xml():
    with pytest.raises(ProviderError):
        CbrXmlProvider().parse(b"<not xml")


def test_cbr_network_error(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("нет сети")

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(ProviderError):
        CbrXmlProvider().parse(b"<not xml")


def test_cbr_uses_response(monkeypatch):
    class FakeResponse:
        content = SAMPLE_XML

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse())
    assert "USD" in CbrXmlProvider().get_rates()


@pytest.mark.parametrize("make_provider", [
    lambda rates: StaticRateProvider(rates),
    lambda rates: StaticRateProvider.demo(),
])
def test_any_provider_has_same_interface(make_provider, rates):
    provider = make_provider(rates)
    assert isinstance(provider, RateProvider)
    assert provider.get_rate("usd").code == "USD"
    with pytest.raises(NotFoundError):
        provider.get_rate("XXX")


# --- Задание 4 (Новые тесты) ---

# 1. Разбор num_code из SAMPLE_XML
def test_parse_num_code():
    # ВНИМАНИЕ: у CbrXmlProvider.parse() нет декоратора @staticmethod, 
    # поэтому его нужно вызывать у экземпляра класса.
    provider = CbrXmlProvider()
    rates = provider.parse(SAMPLE_XML)
    
    assert "USD" in rates
    assert rates["USD"].num_code == "840"
    # ИСПРАВЛЕНО: значение из SAMPLE_XML равно 80,5000
    assert rates["USD"].value == Decimal("80.5000") 


# 2. requests.Timeout через monkeypatch
def test_provider_timeout(monkeypatch):
    def mock_get(*args, **kwargs):
        raise requests.Timeout("Время вышло")
    
    # Подменяем requests.get внутри модуля providers
    monkeypatch.setattr("app.providers.requests.get", mock_get)
    
    provider = CbrXmlProvider(timeout=5)
    with pytest.raises(ProviderError, match="Сервер ЦБ РФ не ответил за 5 секунд"):
        provider.get_rates()


# 3. skipped_count на XML с одной повреждённой записью
def test_provider_skipped_count():
    # XML без лишних отступов и пробелов, чтобы линтер не ругался
    xml_with_error = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="31.10.2026">
<Valute>
<NumCode>840</NumCode>
<CharCode>USD</CharCode>
<Nominal>1</Nominal>
<Name>Доллар</Name>
<Value>90,0</Value>
</Valute>
<Valute>
<NumCode>978</NumCode>
<CharCode>EUR</CharCode>
<Nominal>abc</Nominal>
<Name>Евро</Name>
<Value>100,0</Value>
</Valute>
</ValCurs>
"""

    provider = CbrXmlProvider()
    rates = provider.parse(xml_with_error)
    
    assert len(rates) == 1              # Загрузился только USD
    assert "EUR" not in rates
    assert provider.skipped_count == 1  # Одна запись (EUR) пропущена