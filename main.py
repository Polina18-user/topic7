"""Консольный интерфейс трекера курсов валют."""
import sys

from app.exceptions import AppError, ProviderError
from app.providers import CbrXmlProvider, RateProvider, StaticRateProvider
from app.services import CurrencyTracker

MENU = """
1. Зарегистрироваться
2. Список валют
3. Подписаться на валюту
4. Отписаться от валюты
5. Мои курсы
6. Подписчики валюты
0. Выход
"""


def choose_provider() -> RateProvider:
    if "--offline" in sys.argv:
        return StaticRateProvider.demo()
    return CbrXmlProvider()


def ask_user_id() -> int:
    return int(input("Ваш id: "))


def main() -> None:
    provider = choose_provider()
    tracker = CurrencyTracker(provider)

    print("Синхронизация справочника валют...")
    try:
        tracker.sync_currencies()
    except ProviderError as exc:
        print(f"\nОшибка: {exc}")
        answer = input("Перейти в автономный режим? (y/n): ").strip().lower()
        if answer == 'y':
            print("Переключение на автономный режим...")
            provider = StaticRateProvider.demo()
            tracker = CurrencyTracker(provider)
            tracker.sync_currencies()  # В офлайн-режиме это не вызовет ошибку
            print("Готово.")
        else:
            print("Завершение работы.")
            return
    else:

        print("Синхронизация прошла успешно.")
    finally:
        print("--- Синхронизация завершена ---")


    try:
        while True:
            print(MENU)
            try:
                choice = input("Выберите пункт: ").strip()
            except EOFError:
                print("\nДо свидания")
                break

            try:
                if choice == "1":
                    user = tracker.register_user(input("Имя: "), input("Email: "))
                    print(f"Зарегистрирован: {user} (id={user.id})")
                elif choice == "2":
                    for currency in tracker.currencies:
                        print(currency)
                elif choice == "3":
                    tracker.subscribe(ask_user_id(), input("Код валюты: "))
                    print("Подписка оформлена")
                elif choice == "4":
                    tracker.unsubscribe(ask_user_id(), input("Код валюты: "))
                    print("Подписка отменена")
                elif choice == "5":
                    try:
                        rates = tracker.get_user_rates(ask_user_id())
                        # Сортируем от дорогих к дешевым
                        for rate in sorted(rates, reverse=True):
                            print(rate)
                    except ProviderError as exc:
                        print(f"\nНе удалось обновить курсы: {exc}")
                        print("Возврат в главное меню.")
                elif choice == "6":
                    code = input("Код валюты: ")
                    subscribers = tracker.get_subscribers(code)
                    if not subscribers:
                        print("Нет подписчиков")
                    else:
                        print(f"Подписчики {code.strip().upper()}:")
                        for user in subscribers:
                            print(f"  {user}")
                elif choice == "0":
                    print("До свидания")
                    break
                else:
                    print("Нет такого пункта")
            except AppError as exc:
                # Ловим только наши доменные ошибки, не трогая системные
                print(f"Ошибка: {exc}")
            except ValueError:
                # Ловим ошибку преобразования int(input()) в ask_user_id
                print("Ошибка: id должен быть целым числом")

    except KeyboardInterrupt:
        print("\nДо свидания")


if __name__ == "__main__":
    main()