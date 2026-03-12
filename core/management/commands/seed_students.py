from django.core.management.base import BaseCommand
import random
from datetime import date, timedelta
from core.models import School, Grade, Class, Student, StudentProfile

class Command(BaseCommand):
    help = "Seed the database with 30 students using random Kenyan names and varying grades."

    def handle(self, *args, **options):
        # 1. Get Schools (ID >= 2)
        schools = School.objects.filter(id__gte=2)
        if not schools.exists():
            self.stdout.write(self.style.WARNING("No schools found with ID >= 2."))
            return

        grade_choices = [
            'Play Group', 'PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3',
            'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9'
        ]

        # Kenyan Names logic
        kenyan_male_names = [
            "Otieno", "Kamau", "Juma", "Kibet", "Mwangi", "Maina", "Kariuki", 
            "Mutua", "Musyoka", "Wanyama", "Odhiambo", "Anyona", "Makori", 
            "Momanyi", "Sagini", "Onchiri", "Omondi", "Kimani"
        ]
        kenyan_female_names = [
            "Akinyi", "Atieno", "Wanjiru", "Njeri", "Chebet", "Cherotich", 
            "Mumbua", "Faith", "Zawadi", "Neema", "Amani", "Halima", 
            "Fatuma", "Asha", "Mariam", "Nyanchoka", "Kerubo", "Moraa"
        ]
        kenyan_surnames = [
            "Omondi", "Njau", "Gicheru", "Njoroge", "Karanja", "Musa", 
            "Bakari", "Ali", "Opiyo", "Wafula", "Simiyu", "Kiptoo"
        ]

        total_seeded = 0
        current_year = date.today().year

        for school in schools:
            self.stdout.write(f"Seeding data for school: {school.name}...")
            
            # School-specific prefix for Adm No
            prefix = "".join([word[0] for word in school.name.split() if word]).upper()[:3]
            if not prefix: prefix = "SCH"

            # 2. Create Grades for this school
            grades = []
            for g_name in grade_choices:
                g, _ = Grade.objects.get_or_create(name=g_name, school=school)
                grades.append(g)

            # 3. Create Classes for this school
            classes = []
            for g in grades:
                c, _ = Class.objects.get_or_create(name=f"{g.name} Alpha", grade=g, school=school)
                classes.append(c)

            # 4. Create 100 Students (60:40 ratio)
            males_to_create = 60
            females_to_create = 40
            
            students_data = []
            for _ in range(males_to_create):
                students_data.append(('male', random.choice(kenyan_male_names)))
            for _ in range(females_to_create):
                students_data.append(('female', random.choice(kenyan_female_names)))
            
            random.shuffle(students_data)

            for i, (gender, first_name) in enumerate(students_data):
                middle_name = random.choice(kenyan_male_names + kenyan_female_names)
                last_name = random.choice(kenyan_surnames)
                adm_no = f"{prefix}-{2000 + i}" # Start from 2000 to differentiate from school 1
                
                # Random DOB between 4 and 15 years ago
                birth_year = current_year - random.randint(4, 15)
                date_of_birth = date(birth_year, random.randint(1, 12), random.randint(1, 28))
                
                joined_date = date.today() - timedelta(days=random.randint(0, 365*2))
                location = random.choice(["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"])

                student = Student.objects.create(
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    adm_no=adm_no,
                    date_of_birth=date_of_birth,
                    joined_date=joined_date,
                    gender=gender,
                    location=location
                )

                # Assigned class (ensure all grades covered first then random)
                if i < len(classes):
                    assigned_class = classes[i]
                else:
                    assigned_class = random.choice(classes)

                # Fee balance logic
                rand_val = random.random()
                if rand_val < 0.2:
                    fee_balance = random.randint(-5000, -500)
                elif rand_val < 0.8:
                    fee_balance = random.randint(1000, 20000)
                else:
                    fee_balance = 0

                StudentProfile.objects.create(
                    student=student,
                    class_id=assigned_class,
                    school=school,
                    fee_balance=fee_balance,
                    discipline=random.randint(60, 100)
                )
                total_seeded += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {total_seeded} students across {schools.count()} schools."))
