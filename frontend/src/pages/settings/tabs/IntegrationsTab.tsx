import React, { FC, useState } from "react";
import { StripeStatusType } from "../../../types/stripe-type";
import { useQuery } from "react-query";
import { StripeIntegration } from "../../../integrations/api";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col } from "antd";

import { AppCard } from "../components/AppCard";

const IntegrationsTab: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);

  const fetchStripeConnect = async (): Promise<StripeStatusType> =>
    StripeIntegration.getStripeConnectionStatus().then((data) => {
      return data;
    });

  const { status, error, data, isLoading } = useQuery<StripeStatusType>(
    ["stripeIntegration"],
    fetchStripeConnect
  );

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
      <Typography.Title level={2}>Integrations</Typography.Title>

      <Row gutter={[24, 24]}>
        {data &&
          [1].map((item, index) => {
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
    </div>
  );
};

export default IntegrationsTab;
