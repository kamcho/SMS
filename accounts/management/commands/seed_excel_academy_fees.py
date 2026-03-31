from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import School, Grade, Term
from accounts.models import FeeStructure, AdditionalCharges, AdmissionFee

class Command(BaseCommand):
    help = "Seed the fee structures for Excel Academy according to the defined policy."

    def handle(self, *args, **options):
        try:
            school = School.objects.get(id=1) # Excel Academy
        except School.DoesNotExist:
            self.stdout.write(self.style.ERROR("School Excel Academy (ID 1) not found."))
            return
            
        terms = Term.objects.filter(id__in=[2, 3, 4]) # 2: Term 1, 3: Term 2, 4: Term 3
        if not terms.exists():
             self.stdout.write(self.style.ERROR("Required Terms (IDs 2, 3, 4) not found."))
             return
        
        # Define Day Scholar Tiers according to the provided image/policy
        tiers = [
            {
                'name': 'ECDE (Playgroup, PP1, PP2)',
                'grade_names': ['Play Group', 'PP1', 'PP2'],
                'amounts': {2: 10700, 3: 10000, 4: 10000}
            },
            {
                'name': 'Grade 1-3',
                'grade_names': ['Grade 1', 'Grade 2', 'Grade 3'],
                'amounts': {2: 15700, 3: 15000, 4: 15000}
            },
            {
                'name': 'Grade 4-6',
                'grade_names': ['Grade 4', 'Grade 5', 'Grade 6'],
                'amounts': {2: 16700, 3: 16000, 4: 16000}
            },
            {
                'name': 'Junior School (Grade 7-8)',
                'grade_names': ['Grade 7', 'Grade 8'],
                'amounts': {2: 20000, 3: 20000, 4: 20000}
            },
            {
                'name': 'Junior School (Grade 9)',
                'grade_names': ['Grade 9'],
                'amounts': {2: 23000, 3: 23000, 4: 23000}
            }
        ]
        
        boarding_final_amount = 25000
        
        # 1. Day Scholar Structures (Tiered)
        for term in terms:
            self.stdout.write(f"Propagating Day Scholar fees for {term.name}...")
            for tier in tiers:
                grade_objs = Grade.objects.filter(name__in=tier['grade_names'])
                if not grade_objs.exists():
                    self.stdout.write(self.style.WARNING(f"  Warning: Grades {tier['grade_names']} not found."))
                    continue
                    
                day_amount = tier['amounts'].get(term.id)
                
                # We use get_or_create to allow multi-run
                fs_day, created = FeeStructure.objects.get_or_create(
                    school=school,
                    term=term,
                    student_type='day',
                    name=tier['name'],
                    defaults={'amount': Decimal(day_amount)}
                )
                if not created:
                    fs_day.amount = Decimal(day_amount)
                fs_day.grade.set(grade_objs)
                fs_day.save()
            
            # 2. Boarder Structure (Fixed 25,000 across ALL grades)
            self.stdout.write(f"Propagating Boarder fees for {term.name}...")
            all_grades = Grade.objects.all()
            fs_boarder, created = FeeStructure.objects.get_or_create(
                school=school,
                term=term,
                student_type='boarder',
                name="General Boarding Fee",
                defaults={'amount': Decimal(boarding_final_amount)}
            )
            if not created:
                fs_boarder.amount = Decimal(boarding_final_amount)
            fs_boarder.grade.set(all_grades)
            fs_boarder.save()
            
        # Additional Charges for Junior School (7, 8, 9)
        junior_grades = Grade.objects.filter(name__in=['Grade 7', 'Grade 8', 'Grade 9'])
        
        # Lab Fee
        char_lab, _ = AdditionalCharges.objects.get_or_create(
            school=school,
            name="Laboratory/Technical Materials",
            defaults={'amount': Decimal('3000.00')}
        )
        char_lab.amount = Decimal('3000.00')
        char_lab.grades.set(junior_grades)
        char_lab.save()
        
        # CBC Materials
        char_cbc, _ = AdditionalCharges.objects.get_or_create(
            school=school,
            name="CBC Materials/Services",
            defaults={'amount': Decimal('1500.00')}
        )
        char_cbc.amount = Decimal('1500.00')
        char_cbc.grades.set(junior_grades)
        char_cbc.save()
        
        # Admission Fee
        AdmissionFee.objects.all().delete()
        AdmissionFee.objects.create(amount=Decimal('5000.00'))
        
        self.stdout.write(self.style.SUCCESS(f"Fee structures and additional charges successfully seeded for {school.name}."))
