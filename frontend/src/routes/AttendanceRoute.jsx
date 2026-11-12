import { Navigate, Outlet } from "react-router-dom";

import { routes } from "../pages/auth/auth.constants";
import { getStorage } from "../pages/auth/auth.util";

export default function AdminRoute() {
    const role = getStorage().getItem("role");
   
    if(role !== "attendance") {
         return <Navigate to={routes[role]} replace />
    }
    
    return <Outlet />;
}