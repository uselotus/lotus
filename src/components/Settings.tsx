import React, { FC } from "react";
import "./Settings.css";
import { StripeStatusType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";
import { StripeConnect } from "../api/api";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { loadEnv } from "vite";

const Settings: FC = () => {
  const navigate = useNavigate();
  const fetchStripeConnect = async (): Promise<StripeStatusType | void> => {
    StripeConnect.getStripeConnectionStatus().then((data) => {
      return data;
    });
  };

  const { status, error, data } = useQuery<StripeStatusType | void>(
    "stripeConnect",
    fetchStripeConnect
  );

  const handleConnectWithStripeClick = () => {
    const client_id: string = import.meta.env.VITE_STRIPE_CLIENT;
    console.log(import.meta.env.NODE_ENV);
    let path: string =
      "https://connect.stripe.com/oauth/authorize?response_type=code&client_id=" +
      client_id +
      "&scope=read_write&redirect_uri=" +
      import.meta.env.VITE_API_URL +
      "redirectstripe";
    console.log(path);
    location.href = path;
  };
  return (
    <div>
      <h1>Settings</h1>
      <div>
        {data?.connected ? (
          <div>
            <p>Connected to Stripe &#x2705;</p>{" "}
          </div>
        ) : (
          <div>
            <p>Not Connected to Stripe </p>{" "}
            <a
              className="stripe-connect slate"
              onClick={handleConnectWithStripeClick}
            >
              <span>Connect with</span>
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default Settings;
