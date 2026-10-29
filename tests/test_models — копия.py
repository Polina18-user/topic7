
from datetime import date
from decimal import Decimal
from app.models import User, Currency, Rate

u = User("anna", "a@ex.ru")
print(repr(u), "|", str(u), "|", u == u, len({u, u}))
usd = Currency("USD", "Доллар США")
print(repr(usd), "|", usd, "|", u == usd)        # ... | USD — Доллар США | False
jpy = Rate("JPY", "Японских иен", 100, Decimal("53.0"), date(2026, 10, 27))
print(jpy, "|", jpy.per_unit)                    # 100 JPY = 53.0 RUB на 27.10.2026 | 0.53