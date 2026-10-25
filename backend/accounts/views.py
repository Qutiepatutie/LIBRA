import requests

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import signing

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import UserLogin
from .models import UserProfile, education_level_for_program

from .serializers import UserLoginSerializer

# Only school-issued Google accounts may sign in; the domain decides the role.
GOOGLE_ALLOWED_DOMAINS = {
    "student.fatima.edu.ph": "student",
    "fatima.edu.ph": "faculty",
}
GOOGLE_SIGNUP_SALT = "accounts.google-signup"
GOOGLE_SIGNUP_MAX_AGE = 15 * 60

def issue_tokens(user):
    refresh = RefreshToken.for_user(user)

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserLoginSerializer(user).data
    }

def google_claims_from_code(code):
    # Exchange the popup's auth code, then verify the ID token's signature and audience.
    token_resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": "postmessage",
        "grant_type": "authorization_code",
    }, timeout=10)
    token_resp.raise_for_status()

    return id_token.verify_oauth2_token(
        token_resp.json()["id_token"],
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )

def email_domain(email):
    return email.rpartition("@")[2]

@api_view(["POST"])
def login_user(request):
    email = request.data.get("email")
    password = request.data.get("password")

    try:
        user = UserLogin.objects.get(email=email)
    except UserLogin.DoesNotExist:
        return Response({"message":"Invalid Credentials"}, status=status.HTTP_404_NOT_FOUND)

    if not user.check_password(password):
        return Response({"message":"Invalid Credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(issue_tokens(user), status=status.HTTP_200_OK)

@api_view(["POST"])
def google_login(request):
    code = request.data.get("code")

    if not code:
        return Response({"message": "Missing Google code"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        claims = google_claims_from_code(code)
    except (requests.RequestException, KeyError, ValueError):
        return Response({"message": "Google sign-in failed"}, status=status.HTTP_401_UNAUTHORIZED)

    email = claims.get("email", "").lower()

    if not claims.get("email_verified") or email_domain(email) not in GOOGLE_ALLOWED_DOMAINS:
        return Response({"message": "Use your Fatima email"}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = UserLogin.objects.get(email=email)
    except UserLogin.DoesNotExist:
        # Signed proof of the verified email, redeemed by register_user.
        return Response({
            "message": "No account yet",
            "email": email,
            "google_token": signing.dumps({"email": email}, salt=GOOGLE_SIGNUP_SALT),
        }, status=status.HTTP_404_NOT_FOUND)

    return Response(issue_tokens(user), status=status.HTTP_200_OK)

@api_view(["POST"])
def register_user(request):
    first_name = request.data.get('first_name')
    middle_name = request.data.get('middle_name')
    last_name = request.data.get('last_name')
    sex = request.data.get('sex')
    id_number = request.data.get('id_number')
    program = request.data.get('program')
    email = request.data.get('email')
    password = request.data.get('confirm_password')
    role = request.data.get('role')

    if not all([first_name, last_name, id_number, email, password]):
        return Response({"message": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

    if UserLogin.objects.filter(email=email).exists():
        return Response({"message": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

    if UserProfile.objects.filter(id_number=id_number).exists():
        return Response({"message": "ID number already exists"}, status=status.HTTP_400_BAD_REQUEST)

    user = UserLogin.objects.create_user(
        email = email,
        password = password,
        role = role
    )

    UserProfile.objects.create(
        user = user,
        first_name = first_name,
        middle_name = middle_name,
        last_name = last_name,
        sex = sex,
        id_number = id_number,
        program = program,
        education_level = education_level_for_program(program),
    )

    return Response({"message": "Registered Successfully"}, status=status.HTTP_201_CREATED)

@api_view(["POST"])
def change_password(request):
    email = request.data.get("email")
    newPass = request.data.get("newPass")

    try:
        user = UserLogin.objects.get(email=email)
    except UserLogin.DoesNotExist:
        return Response({"message":"Email does not exist"}, status=status.HTTP_404_NOT_FOUND)

    if check_password(newPass, user.password):
        return Response({"message": "Old password can\'t be the new password"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(newPass)
    user.save()

    return Response({"message":"Password Changed Successfully"}, status=status.HTTP_200_OK)