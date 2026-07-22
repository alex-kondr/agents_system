def add_employee(employees: dict) -> dict:
    username = input("Введіть логін користувача: ")
    name = input("Введіть ім'я працівника: ")
    position = input("Введіть посаду працівника: ")
    salary = input("Введіть ЗП: ")
    start_date = input("Введіть дату початку роботи у форматі '01.01.2024': ")
    password = input("Введіть пароль для працівника: ")

    if username not in employees:
        employees[username] = {
            "position": position,
            "salary": salary,
            "name": name,
            "start_date": start_date,
            "password": password
        }
        print("Працівника успішно зареєстровано в системі.")
    else:
        print("Такий логін вже зареєстрований в системі.")

    return employees


def del_employee(employees: dict) -> dict:
    username = input("Введіть логін працівника для видалення: ")
    if username in employees:
        del employees[username]
        print(f"Користувача з логіном '{username}' успішно видалено.")
    else:
        print("Такого користувача немає в системі.")

    return employees


def show_employees(employees: dict) -> None:
    for username in employees:
        print(f"Користувач з логіном '{username}' має ім'я {employees[username]['name']} почав свою роботу '{employees[username]['start_date']}'")


def change_salary(employees: dict) -> dict:
    username = input("Введіть логін працівника: ")
    salary = input("Введіть нове значення ЗП: ")
    if username in employees:
        employees[username]["salary"] = salary
        print(f"ЗП для користувача з логіном '{username}' змінено.")
    else:
        print("Такого користувача немає в системі.")

    return employees


def change_position(employees: dict) -> dict:
    username = input("Введіть логін працівника: ")
    position = input("Введіть нову посаду: ")
    if username in employees:
        employees[username]["position"] = position
        print(f"Посаду для користувача з логіном '{username}' змінено.")
    else:
        print("Такого користувача немає в системі.")

    return employees
