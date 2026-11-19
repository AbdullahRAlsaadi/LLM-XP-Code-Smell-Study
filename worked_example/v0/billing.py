class Customer:
    def __init__(self, name, years, orders, vip):
        self.name = name
        self.years = years
        self.orders = orders
        self.vip = vip


class Invoice:
    def __init__(self, number, amount):
        self.number = number
        self.amount = amount

    def final_amount(self, rate):
        return self.amount * (1 - rate)
