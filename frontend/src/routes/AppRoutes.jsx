import { Routes, Route } from "react-router-dom" 

import AuthPage from "../pages/auth/AuthPage"
import MainLayout from "../layouts/MainLayout"
import ProtectedRoute from "./ProtectedRoute.jsx"
import AdminRoute from "./AdminRoute.jsx"
import AttendanceRoute from "./AttendanceRoute.jsx"

import Library from "../pages/library/Library.jsx"

import UserDashboard from "../pages/user/UserDashboard.jsx"
import BorrowingHistory from "../pages/user/BorrowingHistory.jsx"
import BorrowedBooks from "../pages/user/borrowedBooks/BorrowedBooks.jsx"
import RoomReservation from "../pages/user/roomReservation/RoomReservation.jsx"

import AdminLayout from "../layouts/AdminLayout.jsx"
import Circulation from "../pages/admin/dashboard/Circulation.jsx"
import Borrowers from "../pages/admin/dashboard/Borrowers.jsx"
import Inventory from "../pages/admin/dashboard/Inventory.jsx"
import History from "../pages/admin/history/History.jsx"
import AddBook from "../pages/admin/addbook/AddBook.jsx"
import AdminBorrowers from "../pages/admin/admission/AdminBorrowers.jsx"
import RoomReservations from "../pages/admin/admission/RoomReservations.jsx"

import Attendance from "../pages/attendance/Attendance.jsx"

export default function AppRoutes() {

  return (
    <Routes>
        <Route path ="/" element={<AuthPage />} />

        <Route element= { <ProtectedRoute /> } >
          <Route element={<AttendanceRoute />} >
               <Route path="/attendance" element = {<Attendance />} />
          </Route>
          <Route element= {<MainLayout />}>
            <Route path="/dashboard" element={<UserDashboard/>} />
            <Route path="/history" element={<BorrowingHistory/>} />
            <Route path="/library" element = {<Library />} />
            <Route path="/borrowed-books" element = {<BorrowedBooks />} />
            <Route path="/room-reservation" element={<RoomReservation />} />
            
            <Route  element = {<AdminRoute />} >
                <Route path ="/admin/dashboard" element={<AdminLayout />}>
                    <Route path="circulation" element= {<Circulation />} />
                    <Route path="borrowers" element= {<Borrowers />} />
                    <Route path="inventory" element= {<Inventory />} />
                </Route>
                
                <Route path="/admin/admission" element={<AdminLayout />}>
                    <Route path="borrowers" element= {<AdminBorrowers />} />
                    <Route path="return-books" element= {<AdminBorrowers />} />
                    <Route path="reserve-rooms" element= {<RoomReservations />} />
                </Route>
                
                <Route path="/admin/history" element={<AdminLayout />}>
                    <Route path="books" element= {<History />} />
                    <Route path="rooms" element= {<History />} />
                </Route>
                <Route path="/admin/add-book" element = {<AddBook />} />
            </Route>
          </Route>    
        </Route>
    </Routes>
  )
}
