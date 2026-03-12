import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Student
from accounts.models import Payment

class Command(BaseCommand):
    help = 'Seeds random fee payments for testing'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No user found to record payments.'))
            return

        students = list(Student.objects.all())
        if not students:
            self.stdout.write(self.style.ERROR('No students found.'))
            return

        methods = ['Cash', 'Mpesa', 'Bank', 'Cheque']
        payment_count = 50
        
        self.stdout.write(f'Seeding {payment_count} random payments...')

        for i in range(payment_count):
            student = random.choice(students)
            amount = random.randint(500, 15000)
            method = random.choice(methods)
            
            # Random date within the last 6 months
            days_ago = random.randint(0, 180)
            date_paid = datetime.now().date() - timedelta(days=days_ago)
            
            # Random reference for non-cash payments
            reference = None
            if method != 'Cash':
                letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                nums = '0123456789'
                reference = ''.join(random.choice(letters + nums) for _ in range(10))

            try:
                Payment.objects.create(
                    student=student,
                    amount=amount,
                    method=method,
                    reference=reference,
                    date_paid=date_paid,
                    recorded_by=user
                )
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'Created {i + 1} payments...')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to create payment {i+1}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {payment_count} random payments.'))
