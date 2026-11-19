def celsius_to_fahrenheit(celsius):
    return celsius * 9 / 5 + 32


def fahrenheit_to_celsius(fahrenheit):
    return (fahrenheit - 32) * 5 / 9


def describe_temperature(celsius):
    if celsius < 10:
        return "cold"
    if celsius < 25:
        return "mild"
    return "hot"
