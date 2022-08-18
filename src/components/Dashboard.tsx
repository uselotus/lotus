import React, { FC } from "react";
import logo_large from "../assets/images/logo_large.jpg";

const Dashboard: FC = () => {
  return (
    <div>
      <h1 className="bg-grey1">Dashboard</h1>
      <img src={logo_large} alt="lotus" />
    </div>
  );
};

export default Dashboard;
