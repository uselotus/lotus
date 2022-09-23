import React, { FC } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/Login";
import Register from "../pages/Registration";

const ExternalRoutes: FC = () => {
  return (
    <Routes>
      <Route path="/register" element={<Register />} />
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<Login />} />
    </Routes>
  );
};

export default ExternalRoutes;
