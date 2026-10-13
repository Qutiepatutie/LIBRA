from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import EducationLevel, UserProfile, education_level_for_program


class EducationLevelForProgramTests(TestCase):
    def test_maps_program_to_education_level(self):
        cases = {
            'BS in Computer Science': EducationLevel.COLLEGE,
            'STEM': EducationLevel.SENIOR_HIGH,
            'HUMSS': EducationLevel.SENIOR_HIGH,
            'Unknown Program': '',
            '': '',
            None: '',
        }
        for program, expected in cases.items():
            with self.subTest(program=program):
                self.assertEqual(education_level_for_program(program), expected)


class RegisterEducationLevelTests(TestCase):
    def register(self, program, id_number):
        return APIClient().post(reverse('register_users'), {
            'first_name': 'Ana', 'last_name': 'Cruz', 'sex': 'female',
            'id_number': id_number, 'program': program,
            'email': f'{id_number}@example.com', 'confirm_password': 'pass12345',
            'role': 'student',
        }, format='json')

    def test_register_assigns_education_level_from_program(self):
        for program, id_number, expected in [
            ('BS in Nursing', '01230001234', EducationLevel.COLLEGE),
            ('ABM', '04230001234', EducationLevel.SENIOR_HIGH),
        ]:
            with self.subTest(program=program):
                self.assertEqual(self.register(program, id_number).status_code, 201)
                profile = UserProfile.objects.get(id_number=id_number)
                self.assertEqual(profile.education_level, expected)
