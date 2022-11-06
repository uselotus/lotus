import AppRoutes from "./config/Routes";
import { Authentication } from "./api/api";
import { useQuery } from "react-query";
import ExternalRoutes from "./config/ExternalRoutes";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "@tremor/react/dist/esm/tremor.css";
import LoadingSpinner from "./components/LoadingSpinner";
import React from "react";
import { PlanProvider } from "./context/PlanContext";
import { useNavigate, useLocation } from "react-router-dom";

const publicRoutes = [
  "/login",
  "/register",
  "/reset-password",
  "/set-new-password",
];

function App() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const fetchSessionInfo = async (): Promise<{ isAuthenticated: boolean }> =>
    Authentication.getSession()
      .then((res) => {
        return res;
      })
      .catch((error) => {
        if (
          error?.response &&
          error?.response?.status === 401 &&
          !publicRoutes.includes(pathname)
        ) {
          navigate("/login");
        }
        return error;
      });

  const { data: sessionData, isLoading } = useQuery<{
    isAuthenticated: boolean;
  }>(["session"], fetchSessionInfo, { refetchInterval: 60000 });

  const isAuthenticated = isLoading ? false : sessionData?.isAuthenticated;

  const contextClass = {
    success: "bg-[#cca43b] text-[#cca43b]",
  };

  if (isLoading) {
    return <LoadingSpinner />;
  } else {
    if (isAuthenticated) {
      return (
        <div>
          <ToastContainer
            autoClose={1000}
            bodyClassName=" text-gold font-main"
            position="top-center"
          />
          <PlanProvider>
            <AppRoutes />
          </PlanProvider>
        </div>
      );
    } else {
      return (
        <div>
          <ToastContainer
            autoClose={1000}
            toastClassName="rounded-md bg-background font-main"
            bodyClassName=" text-gold font-main"
          />
          <ExternalRoutes />
        </div>
      );
    }
  }
}

export default App;
