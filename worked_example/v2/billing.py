class Customer:
    def __init__(self, name, years, orders, vip):
        self.name = name
        self.years = years
        self.orders = orders
        self.vip = vip

    def discount_rate(self):
        if self.vip and self.years > 5 and self.orders > 100:
            return 0.20
        if self.vip or self.years > 3:
            return 0.10
        if self.orders > 50:
            return 0.05
        return 0.0


class Invoice:
    def __init__(self, number, amount):
        self.number = number
        self.amount = amount

    def customer_discount(self, customer):
        return customer.discount_rate()

    def final_amount(self, rate):
        return self.amount * (1 - rate)
