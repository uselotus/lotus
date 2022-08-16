import React from "react";
import AppRoutes from "./config/Routes";
import "./App.css";
import { Authentication } from "./api/api";
import { useQuery, UseQueryResult } from "react-query";
import Login from "./pages/Login";

function App() {
  const fetchSessionInfo = async (): Promise<{ isAuthenticated: boolean }> =>
    Authentication.getSession().then((res) => {
      console.log(res);
      return res;
    });

  const { data: sessionData, isLoading } = useQuery<{
    isAuthenticated: boolean;
  }>(["session"], fetchSessionInfo);

  const isAuthenticated = isLoading ? false : sessionData?.isAuthenticated;
  console.log(sessionData);
  if (isLoading) {
    return <div>Loading...</div>;
  } else {
    if (isAuthenticated) {
      return <AppRoutes />;
    } else {
      console.log(sessionData, isLoading);
      return <Login />;
    }
  }
}

export default App;
