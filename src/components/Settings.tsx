import React, { FC } from "react";
import connectwithstripe from "../assets/images/connectwithstripe.svg";
import "./Settings.css";
import { StripeStatusType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";
import { StripeConnect } from "../api/api";
import axios from "axios";

const Settings: FC = () => {
  const fetchStripeConnect = async (): Promise<StripeStatusType | void> => {
    StripeConnect.connectStripe().then((data) => {
      console.log(data);
      return data;
    });
  };

  const { status, error, data } = useQuery<StripeStatusType | void>(
    "stripeConnect",
    fetchStripeConnect
  );

  const handleConnectWithStripeClick = () => {
    //reroute to url
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
