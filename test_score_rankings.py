#!/usr/bin/env python
"""
Test script to verify score ranking creation for subject configurations
"""
import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SMS.settings')
django.setup()

from Exam.models import ExamSubjectConfiguration, ScoreRanking
from core.models import AcademicYear, Term, Exam
from users.models import MyUser

def test_score_ranking_creation():
    """Test the automatic creation of score rankings"""
    print("Testing score ranking creation...")
    
    # Check existing configurations
    configs = ExamSubjectConfiguration.objects.all()
    print(f"Found {configs.count()} existing subject configurations")
    
    for config in configs:
        print(f"\nConfiguration: {config}")
        print(f"Grade: {config.subject.grade}")
        print(f"Max Score: {config.max_score}")
        
        # Check if score rankings exist
        rankings = ScoreRanking.objects.filter(subject=config)
        print(f"Score rankings: {rankings.count()}")
        
        for ranking in rankings.order_by('-max_score'):
            print(f"  {ranking.grade}: {ranking.min_score} - {ranking.max_score}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_score_ranking_creation()
