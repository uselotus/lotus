import React, { FC, useState } from "react";
import "./Settings.css";
import { StripeStatusType } from "../types/stripe-type";
import { useQuery } from "react-query";
import { StripeConnect } from "../api/api";
import { useNavigate } from "react-router-dom";

const Settings: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);

  const fetchStripeConnect = async (): Promise<StripeStatusType> =>
    StripeConnect.getStripeConnectionStatus().then((data) => {
      return data;
    });

  const { status, error, data } = useQuery<StripeStatusType>(
    ["stripeConnect"],
    fetchStripeConnect
  );

  const handleConnectWithStripeClick = () => {
    const client_id: string = import.meta.env.VITE_STRIPE_CLIENT;
    const query = new URLSearchParams({
      response_type: "code",
      client_id: import.meta.env.VITE_STRIPE_CLIENT,
      scope: "read_write",
      redirect_uri: import.meta.env.VITE_API_URL + "redirectstripe",
    });
    let path: string = "https://connect.stripe.com/oauth/authorize?" + query;
    window.location.href = path;
  };
  return (
    <div>
      <h1>Settings</h1>
      <div>
        {data?.connected === true ? (
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
