def north_region_summary(sales):
    total = 0
    best = None
    for sale in sales:
        total += sale["amount"]
        if best is None or sale["amount"] > best["amount"]:
            best = sale
    average = total / len(sales) if sales else 0
    return {"total": total, "average": average, "best": best}


def south_region_summary(sales):
    total = 0
    best = None
    for sale in sales:
        total += sale["amount"]
        if best is None or sale["amount"] > best["amount"]:
            best = sale
    average = total / len(sales) if sales else 0
    return {"total": total, "average": average, "best": best}
