import React, { FC, useState } from "react";
import { useQuery } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col } from "antd";
import { PaymentProcessorIntegration } from "../../../../api/api";
import {
  PaymentProcessorStatusType,
  integrationsMap,
} from "../../../../types/payment-processor-type";
import { AppCard } from "../components/AppCard";

const IntegrationsTab: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);
  const { data, isLoading } = useQuery<PaymentProcessorStatusType[]>(
    ["PaymentProcessorIntegration"],
    () =>
      PaymentProcessorIntegration.getPaymentProcessorConnectionStatus().then(
        (res) => res
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
      <Row gutter={[24, 24]} className="flex items-stretch">
        {data &&
          data !== undefined &&
          data.map((item, index) => (
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
            ))}
        <Col span={6} className="h-full">
          <AppCard
            connected={false}
            title="Snowflake"
            description="Sync your data to your Snowflake warehouse"
            icon={integrationsMap.snowflake.icon}
            handleClick={() => navigate("/settings/integrations/snowflake")}
          />
        </Col>
        <Col span={6} className="h-full">
          <AppCard
            connected={false}
            title="Salesforce"
            description="Sync your products, customers, and invoices to Salesforce"
            icon={integrationsMap.salesforce.icon}
            handleClick={() => navigate("/settings/integrations/snowflake")}
          />
        </Col>
      </Row>
      <Divider />
    </div>
  );
};
export default IntegrationsTab;
