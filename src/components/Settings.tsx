import React, { FC, useState } from "react";
import "./Settings.css";
import { StripeStatusType } from "../types/stripe-type";
import { useQuery } from "react-query";
import { StripeConnect } from "../api/api";
import { useNavigate } from "react-router-dom";
import { Divider, Button, Modal } from "antd";

const Settings: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);
  const [visible, setVisible] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");

  const closeModal = () => {
    setVisible(false);
    setApiKey("");
  };

  const fetchStripeConnect = async (): Promise<StripeStatusType> =>
    StripeConnect.getStripeConnectionStatus().then((data) => {
      return data;
    });

  const { status, error, data } = useQuery<StripeStatusType>(
    ["stripeConnect"],
    fetchStripeConnect
  );

  const getKey = () => {
    setVisible(true);
  };

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
      <h1 className="text-3xl font-main mb-10">Settings</h1>
      <div>
        {data?.connected === true ? (
          <div>
            <p className="text-danger p-2">Connected to Stripe &#x2705;</p>{" "}
          </div>
        ) : (
          <div className="items-center">
            <p className="text-danger p-2">Not Connected to Stripe </p>{" "}
            <a
              className="stripe-connect slate"
              onClick={handleConnectWithStripeClick}
            >
              <span>Connect with</span>
            </a>
          </div>
        )}
      </div>
      <Divider />
      <div className="mt-10 flex flex-row">
        <Button onClick={getKey}>New API Key</Button>
      </div>
      <Modal visible={visible} onCancel={closeModal}>
        <div className="flex flex-col">
          <p className="text-2xl font-main">New API Key</p>
          <p className="text-lg font-main">
            Your previous key has been revoked
          </p>
          <p className="text-lg font-main">
            Your new key is: 2j234oujl25hlou234
          </p>
        </div>
      </Modal>
    </div>
  );
};

export default Settings;
