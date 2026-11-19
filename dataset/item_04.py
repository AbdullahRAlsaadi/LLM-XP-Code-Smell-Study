def student_report(students):
    lines = []
    for student in students:
        total = sum(student["grades"])
        count = len(student["grades"])
        average = total / count if count else 0
        status = "PASS" if average >= 60 else "FAIL"
        lines.append(f"{student['name']}: {average:.2f} ({status})")
    return "\n".join(lines)


def employee_report(employees):
    lines = []
    for employee in employees:
        total = sum(employee["scores"])
        count = len(employee["scores"])
        average = total / count if count else 0
        status = "PASS" if average >= 60 else "FAIL"
        lines.append(f"{employee['name']}: {average:.2f} ({status})")
    return "\n".join(lines)
