import json
import logging
from decimal import Decimal
from django.conf import settings
from .models import QuizAttempt, StudentAnswer

logger = logging.getLogger(__name__)

class QuizGradingService:
    """Service to handle bulk evaluation of quiz short-answer responses using AI."""
    
    @staticmethod
    def evaluate_bulk_attempts(attempt_ids=None):
        """Evaluate all ungraded short answers for a list of attempts (or all submitted)."""
        if attempt_ids:
            attempts = QuizAttempt.objects.filter(pk__in=attempt_ids)
        else:
            # All submitted attempts where AI grading is not yet complete
            attempts = QuizAttempt.objects.filter(status='submitted', ai_grading_complete=False)
            
        count = 0
        for attempt in attempts:
            count += QuizGradingService.evaluate_attempt_answers(attempt)
            
        return count

    @staticmethod
    def evaluate_attempt_answers(attempt):
        """Evaluate all ungraded short answers for a specific attempt."""
        try:
            import openai
        except ImportError:
            logger.error("OpenAI library not found for grading.")
            return 0

        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            logger.error("OpenAI API Key not set.")
            return 0

        client = openai.OpenAI(api_key=api_key)
        
        # Select all ungraded short-answer responses for this attempt
        ungraded_answers = attempt.answers.filter(
            question__question_type='short_answer',
            is_graded=False
        ).select_related('question')
        
        graded_count = 0
        for answer in ungraded_answers:
            try:
                max_marks = answer.question.marks
                expected = answer.question.expected_answer or "Accuracy and clarity related to the topic."
                student_text = answer.text_answer or "No answer provided."

                system_instruction = (
                    "You are a strict, objective, and fair academic grader for an e-learning platform. "
                    "You evaluate student short-answer responses based heavily on the 'Model/Expected Answer'.\n\n"
                    "STRICT GRADING RULES:\n"
                    "1. If the student's response is completely irrelevant, nonsensical, or entirely incorrect, you MUST award EXACTLY 0 marks.\n"
                    "2. Do not give 'effort' or 'participation' marks. 0 is the correct score for a completely wrong answer.\n"
                    "3. For partial understanding, award partial marks proportionally up to the Max Marks.\n"
                    "4. If the score is less than Max Marks, identify specific gaps in understanding in your feedback.\n\n"
                    "Respond ONLY with a valid JSON object in this exact format: "
                    "{\"score\": X, \"confidence\": Y, \"feedback\": \"...\"}"
                )

                prompt = (
                    f"Subject: {attempt.quiz.subject.name}\n"
                    f"Question: {answer.question.question}\n"
                    f"Model/Expected Answer: {expected}\n"
                    f"Student Response: {student_text}\n"
                    f"Max Marks: {max_marks}\n"
                )

                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {'role': 'system', 'content': system_instruction},
                        {'role': 'user', 'content': prompt}
                    ],
                    temperature=0.0,
                    max_tokens=300,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)
                
                answer.score_awarded = Decimal(str(result.get('score', 0)))
                answer.ai_confidence = Decimal(str(result.get('confidence', 0.8)))
                answer.ai_feedback = result.get('feedback', '')
                answer.is_graded = True
                answer.save() # This triggers the on_answer_graded signal which calculates totals.
                
                graded_count += 1
            except Exception as e:
                logger.error(f"Error grading answer {answer.pk}: {str(e)}")
                
        # Final pass: check if attempt is now fully graded
        attempt.calculate_score()
        return graded_count
