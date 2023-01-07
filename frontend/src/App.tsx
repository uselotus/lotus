import AppRoutes from "./config/Routes";
import { Authentication, Organization } from "./api/api";
import { useQuery } from "react-query";
import ExternalRoutes from "./config/ExternalRoutes";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "@tremor/react/dist/esm/tremor.css";
import LoadingSpinner from "./components/LoadingSpinner";
import React, { useEffect } from "react";
import { PlanProvider } from "./context/PlanContext";
import { useNavigate, useLocation } from "react-router-dom";
import posthog from "posthog-js";
import useGlobalStore, { IOrgStoreType } from "./stores/useGlobalstore";

//telemetry for cloud version only
if (import.meta.env.VITE_API_URL === "https://api.uselotus.io/") {
  posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
    api_host: "https://app.posthog.com",
  });
}

const publicRoutes = [
  "/login",
  "/register",
  "/reset-password",
  "/set-new-password",
];

function App() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const setOrgInfoToStore = useGlobalStore((state) => state.setOrgInfo);
  const { refetch } = useQuery(
    ["organization"],
    () =>
      Organization.get().then((res) => {
        return res[0];
      }),
    {
      onSuccess: (data) => {
        const storeOrgObject: IOrgStoreType = {
          organization_id: data.organization_id,
          company_name: data.company_name,
          default_currency: data.default_currency
            ? data.default_currency
            : undefined,
          environment: undefined,
          plan_tags: data.plan_tags,
        };

        setOrgInfoToStore(storeOrgObject);
      },
    }
  );
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
          navigate("/");
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
  useEffect(() => {
    if (isAuthenticated) {
      refetch();
    }
  }, [isAuthenticated]);
  if (isLoading) {
    return (
      <div className="flex h-screen">
        <div className="m-auto">
          <LoadingSpinner />
        </div>
      </div>
    );
  } else {
    if (isAuthenticated) {
      return (
        <div>
          <ToastContainer
            autoClose={3000}
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
            autoClose={3000}
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
