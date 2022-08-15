import React, { FC } from "react";
import { Card, Col, Row } from "antd";
import Settings from "../components/Settings";

const ViewSettings: FC = () => {
  const handleConnectWithStripeClick = () => {
    console.log(3);
  };

  return (
    <div>
      <Settings />
    </div>
  );
};

export default ViewSettings;
