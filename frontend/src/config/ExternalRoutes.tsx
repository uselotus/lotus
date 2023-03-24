import React, { FC } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/Login";
import ResetPassword from "../pages/ResetPassword";
import Register from "../pages/Registration";
import SetNewPassword from "../pages/SetNewPassword";
import DemoSignup from "../pages/DemoSignup";

const ExternalRoutes: FC = () => (
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
    <Route path="/login" element={<Login />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/set-new-password" element={<SetNewPassword />} />
    <Route
      path="/*"
      element={
        (import.meta as any).env.VITE_IS_DEMO === "true" ? (
          <Login username="demo" password="demo" />
        ) : (
          <Login />
        )
      }
    />
  </Routes>
);

export default ExternalRoutes;
