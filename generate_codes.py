# generate_codes.py — создаёт одноразовые коды доступа и сохраняет в БД

from access_control import init_access_db, create_access_codes

COUNT = 30
BONUS_ATTEMPTS = 5


def main():
    init_access_db()
    codes = create_access_codes(COUNT, bonus_attempts=BONUS_ATTEMPTS)
    print(f"Создано {len(codes)} кодов (каждый даёт +{BONUS_ATTEMPTS} попыток):\n")
    for c in codes:
        print(c)
    print()


if __name__ == "__main__":
    main()
