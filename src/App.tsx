import React from "react";
import AppRoutes from "./config/Routes";
import "./App.css";
import Cookies from "universal-cookie";
import { Authentication } from "./api/api";
import { useQuery, UseQueryResult } from "react-query";
import Login from "./pages/Login";

const cookies = new Cookies();

function App() {
  const fetchSessionInfo = async (): Promise<{
    isAuthenticated: boolean;
  } | void> => {
    Authentication.getSession().then((res) => {
      return res.data;
    });
  };

  const { data: sessionData, isLoading } = useQuery<{
    isAuthenticated: boolean;
  } | void>(["session"], () => fetchSessionInfo(), {
    // select: (data) => data.isAuthenticated,
    onSuccess: (data) => {},
  });

  const isAuthenticated = isLoading ? false : false;
  if (isLoading) {
    return <div>Loading...</div>;
  } else {
    if (!isAuthenticated) {
      return <AppRoutes />;
    } else {
      console.log(sessionData, isLoading);
      return <Login />;
    }
  }
}

export default App;
