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

function App() {
  const fetchSessionInfo = async (): Promise<{ isAuthenticated: boolean }> =>
    Authentication.getSession().then((res) => {
      return res;
    });

  const { data: sessionData, isLoading } = useQuery<{
    isAuthenticated: boolean;
  }>(["session"], fetchSessionInfo, { refetchInterval: 60000 });

  const isAuthenticated = isLoading ? false : sessionData?.isAuthenticated;
  if (isLoading) {
    return (
      <div className="grid h-screen place-items-center">
        <LoadingSpinner />
      </div>
    );
  } else {
    if (isAuthenticated) {
      return (
        <div>
          <ToastContainer autoClose={1000} />
          <PlanProvider>
            <AppRoutes />
          </PlanProvider>
        </div>
      );
    } else {
      return (
        <div>
          <ToastContainer autoClose={1000} />
          <ExternalRoutes />
        </div>
      );
    }
  }
}

export default App;
