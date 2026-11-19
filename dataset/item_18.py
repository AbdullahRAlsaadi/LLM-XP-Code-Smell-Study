class Member:
    def __init__(self, name, joined_year, borrowed, fines):
        self.name = name
        self.joined_year = joined_year
        self.borrowed = borrowed
        self.fines = fines


class Library:
    def __init__(self, name):
        self.name = name
        self.books = []

    def add_book(self, title):
        self.books.append(title)

    def member_status(self, member, current_year):
        years = current_year - member.joined_year
        if member.fines > 100:
            return f"{member.name}: suspended"
        if years > 10 and member.borrowed > 200:
            return f"{member.name}: gold"
        if years > 5 or member.borrowed > 100:
            return f"{member.name}: silver"
        return f"{member.name}: regular"
