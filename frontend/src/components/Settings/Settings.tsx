import React, { FC, useState } from "react";
import "./Settings.css";
import { StripeStatusType } from "../../types/stripe-type";
import { useQuery } from "react-query";
import { Alerts } from "../../api/api";
import { StripeIntegration } from "../../integrations/api";
import { useNavigate } from "react-router-dom";
import { Divider, Button, Modal, List, Card } from "antd";
import { APIToken } from "../../api/api";

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
    StripeIntegration.getStripeConnectionStatus().then((data) => {
      return data;
    });

  const { status, error, data } = useQuery<StripeStatusType>(
    ["stripeIntegration"],
    fetchStripeConnect
  );

  const {
    status: alertStatus,
    error: webhookError,
    data: webhookData,
  } = useQuery<StripeStatusType>(["urls"], Alerts.getUrls);

  const getKey = () => {
    APIToken.newAPIToken().then((data) => {
      setApiKey(data.api_key);
    });
    setVisible(true);
  };

  const handleConnectWithStripeClick = () => {
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
        <Button onClick={getKey}>Revoke API Key</Button>
      </div>
      <Divider />
      <div className="mt-10 flex flex-row">
        <h2 className="font-main text-xl">Webhooks Urls</h2>
        {/* <List>
          {webhookData?.urls.map((url) => (
            <List.Item>
              <Card>
                <p>{url}</p>
                </Card>}
              </List.Item>
            ))}
        </List> */}
      </div>
      <Modal
        visible={visible}
        footer={
          <Button key="ok" onClick={closeModal}>
            Ok
          </Button>
        }
      >
        <div className="flex flex-col">
          <p className="text-2xl font-main">New API Key</p>
          <p className="text-lg font-main">
            Your previous key has been revoked
          </p>
          <p className="text-lg font-main">
            Your new key is: {apiKey ? apiKey : "Loading..."}
          </p>
          <p></p>
        </div>
      </Modal>
    </div>
  );
};

export default Settings;
