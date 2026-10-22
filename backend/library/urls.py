from django.urls import path
from . import views

urlpatterns =[
    path('addBook/', views.add_books, name='add_book'),
    path('getBooks/', views.get_books, name='get_books'),
    path('editBook/', views.edit_book, name='edit_book'),
    path('borrowBook/', views.borrow_book, name='borrow_book'),
    path('getUserBorrowedBooks/', views.get_user_borrowed_books, name='get_user_borrowed_books'),
    path('getAllBorrowedBooks/', views.get_all_borrowed_books, name='get_all_borrowed_books'),
    path('exportBorrowedBooksCSV/', views.export_borrowed_books_csv, name='export_borrowed_books_csv'),
    path('acceptBorrowedBook/', views.accept_borrowed_book, name='accept_borrowed_book'),
    path('returnBook/', views.return_book, name='return_book'),
    path('cancelBorrowedBook/', views.cancel_borrowed_book, name='cancel_borrowed_book'),
    path('analyticsDashboard/', views.analytics_dashboard, name='analytics_dashboard'), #NOT FINISHED YET
    path('getUserAnalytics/', views.get_user_analytics, name='get_user_analytics'),
    path('getUserCurrentLoans/', views.get_user_current_loans, name='get_user_current_loans'),
    path('getUserBorrowingHistory/', views.get_user_borrowing_history, name='get_user_borrowing_history'),
]
