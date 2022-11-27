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
  const { data, isLoading } = useQuery<PaymentProcessorStatusType[]>(
    ["PaymentProcessorIntegration"],
    () =>
      PaymentProcessorIntegration.getPaymentProcessorConnectionStatus().then(
        (res) => {
          return res;
        }
      )
  );

  const handleConnectWithPaymentProcessorClick = (path: string) => {
    if (path !== "") {
      window.location.href = path;
    }
  };
  return (
    <div>
      <Typography.Title level={2}>Integrations</Typography.Title>
      <Row gutter={[24, 24]}>
        {data &&
          data !== undefined &&
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
