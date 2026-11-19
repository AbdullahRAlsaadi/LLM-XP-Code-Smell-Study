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

    def customer_discount(self, customer):
        if customer.vip and customer.years > 5 and customer.orders > 100:
            return 0.20
        if customer.vip or customer.years > 3:
            return 0.10
        if customer.orders > 50:
            return 0.05
        return 0.0

    def final_amount(self, rate):
        return self.amount * (1 - rate)
