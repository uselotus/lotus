import React, { FC } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/Login";
import OIDCLogin from "../pages/OIDCLogin";
import OIDCAuthorization from "../pages/OIDCAuthorization";
import ResetPassword from "../pages/ResetPassword";
import Register from "../pages/Registration";
import SetNewPassword from "../pages/SetNewPassword";
import DemoSignup from "../pages/DemoSignup";

const ExternalRoutes: FC = () => {
  return (
    <Routes>
      <Route
        path="/register"
        element={
          (import.meta as any).env.VITE_IS_DEMO === "true" ? (
            <DemoSignup />
          ) : (
            <Register />
          )
        }
      />
      <Route path="/login-legacy" element={<Login />} />
      <Route path="/login" element={<OIDCLogin />} />
      <Route path="/authorize" element={<OIDCAuthorization />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/set-new-password" element={<SetNewPassword />} />
      <Route
        path="/*"
        element={
          (import.meta as any).env.VITE_IS_DEMO === "true" ? (
            <Navigate replace to={"/register"} />
          ) : (import.meta as any).env.VITE_USE_OIDC === "true" ? (
            <OIDCLogin />
          ) : (
            <Login />
          )
        }
      />
    </Routes>
  );
};

export default ExternalRoutes;
