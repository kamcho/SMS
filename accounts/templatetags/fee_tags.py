from django import template
from accounts.models import Invoice, FeeStructure

register = template.Library()

@register.simple_tag
def get_student_fee_structure(profile, active_term, active_year):
    if not active_term or not active_year or not profile:
        return None
    s_type = 'boarder' if profile.student.is_boarder else 'day'
    return FeeStructure.objects.filter(
        academic_year=active_year,
        term=active_term,
        school=profile.school,
        student_type=s_type,
        grade=profile.class_id.grade
    ).first()

@register.simple_tag
def get_invoice(student, active_term, active_year):
    if not active_term or not active_year:
        return None
    # Find ANY invoice for this student in this term/year
    return Invoice.objects.filter(
        student=student, 
        fee_structure__academic_year=active_year,
        fee_structure__term=active_term
    ).first()
