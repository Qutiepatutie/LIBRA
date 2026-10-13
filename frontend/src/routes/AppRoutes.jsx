import { Routes, Route } from "react-router-dom" 

import AuthPage from "../pages/auth/AuthPage"
import MainLayout from "../layouts/MainLayout"
import ProtectedRoute from "./ProtectedRoute.jsx"
import AdminRoute from "./AdminRoute.jsx"
import AttendanceRoute from "./AttendanceRoute.jsx"

import UserDashboard from "../pages/user/UserDashboard.jsx"
import BorrowingHistory from "../pages/user/BorrowingHistory.jsx"
import Library from "../pages/user/library/Library.jsx"
import BorrowedBooks from "../pages/user/borrowedBooks/BorrowedBooks.jsx"

import AdminDashboardLayout from "../layouts/AdminDashboardLayout.jsx"
import AdminAdmissionLayout from "../layouts/AdminAdmissionLayout.jsx"
import Circulation from "../pages/admin/dashboard/Circulation.jsx"
import Borrowers from "../pages/admin/dashboard/Borrowers.jsx"
import Inventory from "../pages/admin/dashboard/Inventory.jsx"
import History from "../pages/admin/History.jsx"
import AddBook from "../pages/admin/addbook/AddBook.jsx"
import DiscussionRoom from "../pages/user/DiscussionRoom.jsx"
import AcceptBorrowers from "../pages/admin/admission/AcceptBorrowers.jsx"
import ReturnBooks from "../pages/admin/admission/ReturnBooks.jsx"

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
            <Route path="/discussion-room-reservation" element = {<DiscussionRoom />} />
            
            <Route  element = {<AdminRoute />} >
                <Route path ="/admin/dashboard" element={<AdminDashboardLayout />}>
                    <Route path="circulation" element= {<Circulation />} />
                    <Route path="borrowers" element= {<Borrowers />} />
                    <Route path="inventory" element= {<Inventory />} />
                </Route>
                    <Route path="/admin/admission" element={<AdminAdmissionLayout />}>
                        <Route path="borrowers" element= {<AcceptBorrowers />} />
                        <Route path="return-books" element= {<ReturnBooks />} />
                    </Route>
                <Route path="/admin/history" element = {<History />} />
                <Route path="/admin/add-book" element = {<AddBook />} />
            </Route>
          </Route>    
        </Route>
    </Routes>
  )
}
