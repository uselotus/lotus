import React, { FC, useState } from "react";
import "./Settings.css";
import { StripeStatusType } from "../../types/stripe-type";
import { useQuery } from "react-query";
import { Alerts } from "../../api/api";
import { StripeIntegration } from "../../integrations/api";
import { useNavigate } from "react-router-dom";
import { Divider, Button, Modal, List, Card, Typography, Row, Col } from "antd";
import { APIToken } from "../../api/api";
import { AppCard } from "./components/AppCard";

const IntegrationsTab: FC = () => {
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

  const { status, error, data, isLoading } = useQuery<StripeStatusType>(
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

  console.log("data", data);

  return (
    <div>
      <Typography.Title level={2}>Integrations</Typography.Title>

      <Row gutter={[24, 24]}>
        {data &&
          [1, 2, 3, 4].map((item, index) => {
            return (
              <Col span={6} key={index}>
                <AppCard
                  connected={data.connected}
                  title="Stripe"
                  description="Automatically charge your customers for their subscriptions."
                  icon="https://cdn.neverbounce.com/images/integrations/square/stripe-square.png"
                  handleClick={handleConnectWithStripeClick}
                />
              </Col>
            );
          })}
      </Row>

      <Divider />
      <div className="mt-10 flex flex-row">
        <Button onClick={getKey}>Revoke API Key</Button>
      </div>
      <Divider />
      <div className="mt-10 flex flex-row">
        <Typography.Title level={2}>Webhook URLs</Typography.Title>
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

export default IntegrationsTab;
