from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import EducationLevel, UserLogin, UserProfile, education_level_for_program


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


class GoogleLoginTests(TestCase):
    def google_login(self, claims):
        with patch('accounts.views.google_claims_from_code', return_value=claims):
            return APIClient().post(reverse('google_login'), {'code': 'auth-code'}, format='json')

    def test_rejects_non_fatima_domains(self):
        for email in ['ana@gmail.com', 'ana@notfatima.edu.ph', 'ana@fatima.edu.ph.evil.com']:
            with self.subTest(email=email):
                resp = self.google_login({'email': email, 'email_verified': True})
                self.assertEqual(resp.status_code, 403)

    def test_rejects_unverified_email(self):
        resp = self.google_login({'email': 'ana@student.fatima.edu.ph', 'email_verified': False})
        self.assertEqual(resp.status_code, 403)

    def test_existing_user_gets_tokens(self):
        UserLogin.objects.create_user(email='ana@student.fatima.edu.ph', password='pass12345')
        resp = self.google_login({'email': 'Ana@student.fatima.edu.ph', 'email_verified': True})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertEqual(resp.data['user']['email'], 'ana@student.fatima.edu.ph')

    def test_unknown_user_gets_signup_token(self):
        resp = self.google_login({'email': 'ana@fatima.edu.ph', 'email_verified': True})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data['email'], 'ana@fatima.edu.ph')
        self.assertTrue(resp.data['google_token'])


class RegisterWithGoogleTests(TestCase):
    def register(self, google_token, email='typed@example.com'):
        return APIClient().post(reverse('register_users'), {
            'first_name': 'Ana', 'last_name': 'Cruz', 'sex': 'female',
            'id_number': '01230001234', 'program': 'BS in Nursing',
            'email': email, 'confirm_password': 'pass12345',
            'role': 'admin', 'google_token': google_token,
        }, format='json')

    def test_uses_verified_email_and_domain_role(self):
        with patch('accounts.views.google_claims_from_code',
                   return_value={'email': 'ana@fatima.edu.ph', 'email_verified': True}):
            token = APIClient().post(reverse('google_login'), {'code': 'c'}, format='json').data['google_token']

        self.assertEqual(self.register(token).status_code, 201)
        user = UserLogin.objects.get()
        self.assertEqual(user.email, 'ana@fatima.edu.ph')
        self.assertEqual(user.role, 'faculty')

    def test_rejects_tampered_token(self):
        self.assertEqual(self.register('not-a-real-token').status_code, 400)
        self.assertFalse(UserLogin.objects.exists())
