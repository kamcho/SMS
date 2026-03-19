from django import template

register = template.Library()

@register.filter
def get_attendance_status(student_id, session):
    """
    Get attendance status for a student in a session.
    Returns the attendance record or None if not found.
    """
    if not session:
        return None
    
    # Try to find the attendance record for this student
    try:
        return session.records.filter(student_id=student_id).first()
    except:
        return None

@register.filter
def is_attendance_absent(student_id, session):
    """
    Check if student is marked as absent in the session.
    Returns True if absent, False otherwise.
    """
    record = get_attendance_status(student_id, session)
    if record and record.status == 'Absent':
        return True
    return False

@register.filter
def get_attendance_remarks(student_id, session):
    """
    Get remarks for a student in the session.
    Returns the remarks or empty string.
    """
    record = get_attendance_status(student_id, session)
    if record and record.remarks:
        return record.remarks
    return ''

@register.filter
def get_attendance_status_value(student_id, session):
    """
    Get the status value (Present, Late, etc.) for a student in the session.
    Returns the status or 'Present' as default.
    """
    record = get_attendance_status(student_id, session)
    if record:
        return record.status
    return 'Present'

@register.filter
def should_be_checked(student_id, session):
    """
    Determine if checkbox should be checked for a student.
    Returns True if student should be checked (not absent).
    """
@register.filter
def abs_val(value):
    """
    Returns the absolute value of the argument.
    """
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value
