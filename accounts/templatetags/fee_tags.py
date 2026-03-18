from django import template
from accounts.models import Invoice, FeeStructure

register = template.Library()

@register.simple_tag
def get_student_fee_structure(profile, active_term, active_year=None):
    """
    Returns the fee structure for a student for a given term.
    academic_year is kept for backwards compatibility but ignored.
    """
    if not active_term or not profile:
        return None
    s_type = 'boarder' if profile.student.is_boarder else 'day'
    return FeeStructure.objects.filter(
        term=active_term,
        school=profile.school,
        student_type=s_type,
        grade=profile.class_id.grade
    ).first()

@register.simple_tag
def get_invoice(student, active_term, active_year=None):
    """
    Returns any invoice for this student in the given term.
    academic_year is kept for backwards compatibility but ignored.
    """
    if not active_term:
        return None
    return Invoice.objects.filter(
        student=student,
        fee_structure__term=active_term
    ).first()
