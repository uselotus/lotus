import React, { FC, useState } from "react";
import {
  PaymentProcessorStatusType,
  integrationsMap,
} from "../../../../types/payment-processor-type";
import { useQuery } from "react-query";
import { PaymentProcessorIntegration } from "../../../../api/api";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col } from "antd";

import { AppCard } from "../components/AppCard";

const IntegrationsTab: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);

  const fetchPaymentProcessorConnect = async (): Promise<
    PaymentProcessorStatusType[]
  > =>
    PaymentProcessorIntegration.getPaymentProcessorConnectionStatus().then(
      (data) => {
        return data;
      }
    );

  const { status, error, data, isLoading } = useQuery<
    PaymentProcessorStatusType[]
  >(["PaymentProcessorIntegration"], fetchPaymentProcessorConnect);

  const handleConnectWithPaymentProcessorClick = (path: string) => {
    console.log("path", path);
    if (path !== "") {
      window.location.href = path;
    }
  };

  return (
    <div>
      <Typography.Title level={2}>Integrations</Typography.Title>

      <Row gutter={[24, 24]}>
        {data &&
          data.map((item, index) => {
            return (
              <Col span={6} key={index}>
                <AppCard
                  connected={item.connected}
                  title={integrationsMap[item.payment_provider_name].name}
                  description={
                    integrationsMap[item.payment_provider_name].description
                  }
                  icon={integrationsMap[item.payment_provider_name].icon}
                  handleClick={() =>
                    handleConnectWithPaymentProcessorClick(item.redirect_url)
                  }
                  selfHosted={item.redirect_url === ""}
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
