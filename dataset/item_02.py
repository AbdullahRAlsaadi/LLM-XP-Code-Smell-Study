class Teacher:
    def __init__(self, title, name, email, office, phone):
        self.title = title
        self.name = name
        self.email = email
        self.office = office
        self.phone = phone


class Course:
    def __init__(self, code, students):
        self.code = code
        self.students = students

    def enrolled_count(self):
        return len(self.students)

    def teacher_contact_card(self, teacher):
        lines = [
            f"{teacher.title} {teacher.name}",
            f"Email: {teacher.email}",
            f"Office: {teacher.office}",
            f"Phone: {teacher.phone}",
        ]
        if not teacher.phone:
            lines.append("Contact by email only")
        return "\n".join(lines)
