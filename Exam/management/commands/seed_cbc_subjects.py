from django.core.management.base import BaseCommand
from Exam.models import Course, Subject

class Command(BaseCommand):
    help = 'Seeds KICD CBC subjects for Pre-Primary to Grade 6'

    def handle(self, *args, **kwargs):
        # Define Courses (Categories)
        courses_data = [
            {'name': 'Language & Communication', 'abbreviation': 'LAN'},
            {'name': 'Mathematics & Science', 'abbreviation': 'SCI'},
            {'name': 'Environment & Social', 'abbreviation': 'ENV'},
            {'name': 'Creative & Psychomotor', 'abbreviation': 'ART'},
            {'name': 'Religious & Moral', 'abbreviation': 'REL'},
            {'name': 'Technical & Applied', 'abbreviation': 'TEC'},
        ]

        courses = {}
        for c_data in courses_data:
            course, created = Course.objects.get_or_create(
                name=c_data['name'],
                defaults={'abbreviation': c_data['abbreviation']}
            )
            courses[c_data['name']] = course

            # Play Group
            'Play Group': [
                ('Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Psychomotor and Creative Activities', 'Creative & Psychomotor'),
                ('Religious Education Activities', 'Religious & Moral'),
            ],
            # Pre-Primary (PP1, PP2)
            'PP1': [
                ('Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Psychomotor and Creative Activities', 'Creative & Psychomotor'),
                ('Religious Education Activities', 'Religious & Moral'),
            ],
            'PP2': [
                ('Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Psychomotor and Creative Activities', 'Creative & Psychomotor'),
                ('Religious Education Activities', 'Religious & Moral'),
            ],
            # Lower Primary (Grade 1-3)
            'Grade 1': [
                ('English Language Activities', 'Language & Communication'),
                ('Kiswahili Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Hygiene and Nutrition Activities', 'Mathematics & Science'),
                ('Religious Education Activities', 'Religious & Moral'),
                ('Movement and Creative Activities', 'Creative & Psychomotor'),
            ],
            'Grade 2': [
                ('English Language Activities', 'Language & Communication'),
                ('Kiswahili Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Hygiene and Nutrition Activities', 'Mathematics & Science'),
                ('Religious Education Activities', 'Religious & Moral'),
                ('Movement and Creative Activities', 'Creative & Psychomotor'),
            ],
            'Grade 3': [
                ('English Language Activities', 'Language & Communication'),
                ('Kiswahili Language Activities', 'Language & Communication'),
                ('Mathematical Activities', 'Mathematics & Science'),
                ('Environmental Activities', 'Environment & Social'),
                ('Hygiene and Nutrition Activities', 'Mathematics & Science'),
                ('Religious Education Activities', 'Religious & Moral'),
                ('Movement and Creative Activities', 'Creative & Psychomotor'),
            ],
            # Upper Primary (Grade 4-6)
            'Grade 4': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Science and Technology', 'Mathematics & Science'),
                ('Social Studies', 'Environment & Social'),
                ('Agriculture', 'Technical & Applied'),
                ('Home Science', 'Technical & Applied'),
                ('Creative Arts', 'Creative & Psychomotor'),
                ('Physical and Health Education', 'Creative & Psychomotor'),
                ('Religious Education', 'Religious & Moral'),
            ],
            'Grade 5': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Science and Technology', 'Mathematics & Science'),
                ('Social Studies', 'Environment & Social'),
                ('Agriculture', 'Technical & Applied'),
                ('Home Science', 'Technical & Applied'),
                ('Creative Arts', 'Creative & Psychomotor'),
                ('Physical and Health Education', 'Creative & Psychomotor'),
                ('Religious Education', 'Religious & Moral'),
            ],
            'Grade 6': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Science and Technology', 'Mathematics & Science'),
                ('Social Studies', 'Environment & Social'),
                ('Agriculture', 'Technical & Applied'),
                ('Home Science', 'Technical & Applied'),
                ('Creative Arts', 'Creative & Psychomotor'),
                ('Physical and Health Education', 'Creative & Psychomotor'),
                ('Religious Education', 'Religious & Moral'),
            ],
            # Junior Secondary (Grade 7-9)
            'Grade 7': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Integrated Science', 'Mathematics & Science'),
                ('Health Education', 'Mathematics & Science'),
                ('Pre-Technical Studies', 'Technical & Applied'),
                ('Social Studies', 'Environment & Social'),
                ('Business Studies', 'Technical & Applied'),
                ('Agriculture and Nutrition', 'Technical & Applied'),
                ('Religious Education', 'Religious & Moral'),
                ('Life Skills Education', 'Religious & Moral'),
                ('Physical Education and Sports', 'Creative & Psychomotor'),
                ('Creative Arts and Sports', 'Creative & Psychomotor'),
                ('Optional Subject', 'Technical & Applied'),
            ],
            'Grade 8': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Integrated Science', 'Mathematics & Science'),
                ('Health Education', 'Mathematics & Science'),
                ('Pre-Technical Studies', 'Technical & Applied'),
                ('Social Studies', 'Environment & Social'),
                ('Business Studies', 'Technical & Applied'),
                ('Agriculture and Nutrition', 'Technical & Applied'),
                ('Religious Education', 'Religious & Moral'),
                ('Life Skills Education', 'Religious & Moral'),
                ('Physical Education and Sports', 'Creative & Psychomotor'),
                ('Creative Arts and Sports', 'Creative & Psychomotor'),
                ('Optional Subject', 'Technical & Applied'),
            ],
            'Grade 9': [
                ('English', 'Language & Communication'),
                ('Kiswahili', 'Language & Communication'),
                ('Mathematics', 'Mathematics & Science'),
                ('Integrated Science', 'Mathematics & Science'),
                ('Health Education', 'Mathematics & Science'),
                ('Pre-Technical Studies', 'Technical & Applied'),
                ('Social Studies', 'Environment & Social'),
                ('Business Studies', 'Technical & Applied'),
                ('Agriculture and Nutrition', 'Technical & Applied'),
                ('Religious Education', 'Religious & Moral'),
                ('Life Skills Education', 'Religious & Moral'),
                ('Physical Education and Sports', 'Creative & Psychomotor'),
                ('Creative Arts and Sports', 'Creative & Psychomotor'),
                ('Optional Subject', 'Technical & Applied'),
            ],
        }

        subject_count = 0
        for grade_name, subjects_list in cbc_curriculum.items():
            for s_name, c_name in subjects_list:
                course = courses[c_name]
                subject, created = Subject.objects.get_or_create(
                    name=s_name,
                    grade=grade_name,
                    defaults={'course': course}
                )
                if created:
                    subject_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {subject_count} CBC subjects across {len(cbc_curriculum)} grades.'))
