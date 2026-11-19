users = {}


def register_user(username, email):
    if "@" not in email:
        raise ValueError("Invalid email")
    if email.count("@") != 1:
        raise ValueError("Invalid email")
    if email.startswith("@") or email.endswith("@"):
        raise ValueError("Invalid email")
    if "." not in email.split("@")[1]:
        raise ValueError("Invalid email")
    users[username] = email


def update_email(username, email):
    if "@" not in email:
        raise ValueError("Invalid email")
    if email.count("@") != 1:
        raise ValueError("Invalid email")
    if email.startswith("@") or email.endswith("@"):
        raise ValueError("Invalid email")
    if "." not in email.split("@")[1]:
        raise ValueError("Invalid email")
    users[username] = email
