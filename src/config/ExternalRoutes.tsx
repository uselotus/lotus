import React, { FC } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import CreateOrganization from "../components/Registration/CreateOrganization";
import Login from "../pages/Login";
import 

const ExternalRoutes: FC = () => {
  return (
    <Routes>
      <Route path="/register" element={<CreateOrganization />} />

      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<Login />} />

      <Route path="/settings" element={<ViewSettings />} />
      <Route path="/redirectstripe" element={<StripeRedirect />} />
    </Routes>
  );
};

export default ExternalRoutes;
