from billing import Customer, Invoice


def test_loyal_vip_gets_twenty_percent():
    customer = Customer("Sara", years=6, orders=120, vip=True)
    assert Invoice(1, 1000).customer_discount(customer) == 0.20


def test_vip_or_long_standing_gets_ten_percent():
    customer = Customer("Omar", years=4, orders=10, vip=False)
    assert Invoice(2, 500).customer_discount(customer) == 0.10


def test_frequent_buyer_gets_five_percent():
    customer = Customer("Lina", years=1, orders=60, vip=False)
    assert Invoice(3, 200).customer_discount(customer) == 0.05


def test_final_amount_applies_discount():
    customer = Customer("Sara", years=6, orders=120, vip=True)
    invoice = Invoice(4, 1000)
    assert invoice.final_amount(invoice.customer_discount(customer)) == 800
