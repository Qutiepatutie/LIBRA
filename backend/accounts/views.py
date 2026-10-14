from django.contrib.auth.hashers import check_password

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import UserLogin
from .models import UserProfile, education_level_for_program

from .serializers import UserLoginSerializer

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

    refresh = RefreshToken.for_user(user)

    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    serializer = UserLoginSerializer(user)
    return Response({
        "access": access_token,
        "refresh": refresh_token ,
        "user": serializer.data
    }, status=status.HTTP_200_OK)

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