from django.db import models
from django.dispatch import Signal, receiver
from .models import StudentAnswer, QuizAttempt

# Signal that triggers when an individual answer is graded
answer_graded = Signal()

@receiver(models.signals.post_save, sender=StudentAnswer)
def on_answer_graded(sender, instance, created, **kwargs):
    """Triggered when an individual answer is saved. Checks if it was just graded."""
    # Only act if is_graded is True (and just became True if we wanted to be more precise)
    if instance.is_graded:
        # Check if this was the last ungraded answer for the attempt
        # and update overall quiz score.
        instance.attempt.calculate_score()
        # Optionally fire our custom signal if external apps need it
        answer_graded.send(sender=sender, instance=instance)

@receiver(models.signals.post_save, sender=QuizAttempt)
def on_quiz_attempt_updated(sender, instance, created, **kwargs):
    """Triggered when a quiz attempt's score is updated."""
    # This can be used to sync with main academic record in the future.
    pass
