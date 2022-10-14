import React, { FC } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/Login";
import ResetPassword from "../pages/ResetPassword";
import Register from "../pages/Registration";
import SetNewPassword from "../pages/SetNewPassword";

const ExternalRoutes: FC = () => {
  return (
    <Routes>
      <Route path="/register" element={<Register />} />
      <Route path="/login" element={<Login />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/set-new-password" element={<SetNewPassword />} />
      <Route path="/*" element={<Login />} />
    </Routes>
  );
};

export default ExternalRoutes;
