import React, { FC } from "react";
import connectwithstripe from "../assets/images/connectwithstripe.svg";
import "./Settings.css";
import { StripeStatusType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";
import { StripeConnect } from "../api/api";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const Settings: FC = () => {
  const navigate = useNavigate();
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
    let path: string =
      "https://connect.stripe.com/oauth/authorize?response_type=code&client_id=" +
      import.meta.env.VITE_STRIPE_CLIENT +
      "&scope=read_write";
    location.href = path;
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
