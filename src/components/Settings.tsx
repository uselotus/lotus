import React, { FC } from "react";
import connectwithstripe from "../assets/images/connectwithstripe.svg";
import "./Settings.css";

const Settings: FC = () => {
  const handleConnectWithStripeClick = () => {
    console.log(3);
  };
  return (
    <div>
      <h1>Settings</h1>
      <div>
        <a
          href="#"
          className="stripe-connect slate"
          onClick={handleConnectWithStripeClick}
        >
          <span>Connect with</span>
        </a>
      </div>
    </div>
  );
};

export default Settings;
