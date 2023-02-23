import React, { FC, useState } from "react";
import { useQuery } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col, Modal, Input } from "antd";
// import Nango from "@nangohq/frontend";
import { toast } from "react-toastify";
import { PaymentProcessorIntegration, Organization } from "../../../../api/api";
import {
  PaymentProcessorStatusType,
  integrationsMap,
  PaymentProcessorType,
  PaymentProcessorConnectionRequestType,
  BraintreeConnectionRequestType,
  PaymentProcessorConnectionResponseType,
} from "../../../../types/payment-processor-type";
import { AppCard } from "../components/AppCard";
import useGlobalStore from "../../../../stores/useGlobalstore";

const IntegrationsTab: FC = () => {
  const navigate = useNavigate();
  const [connectedStatus, setConnectedStatus] = useState<boolean>(false);
  const { data, isLoading, refetch } = useQuery<PaymentProcessorStatusType[]>(
    ["PaymentProcessorIntegration"],
    () =>
      PaymentProcessorIntegration.getPaymentProcessorConnectionStatus().then(
        (res) => res
      )
  );
  const org = useGlobalStore((state) => state.org);

  // var nango = new Nango({
  //   publicKey: (import.meta as any).env.VITE_NANGO_PK,
  //   debug: true,
  // }); // Nango Cloud

  const handleConnectWithPaymentProcessorClick = (
    item: PaymentProcessorStatusType
  ) => {
    if (item.payment_provider_name === "stripe") {
      if (item.redirect_url !== "") {
        window.location.href = item.redirect_url;
      }
    } else if (item.payment_provider_name === "braintree") {
      const this_org = org.linked_organizations?.filter(
        (org) => org.current
      )[0];
      var unique_config_key = "";
      if (this_org?.organization_type.toLowerCase() === "production") {
        toast.error("Braintree is not supported in production environment.");
        return;
      } else {
        unique_config_key = "braintree-sandbox";
      }
      // nango
      //   .auth(unique_config_key, item.connection_id)
      //   .then((result) => {
      //     toast.success(
      //       `OAuth flow succeeded for provider "${result.providerConfigKey}"!`
      //     );
      //     console.log("RESULT FROM OAUTH: ", result);
      //     const inner_data: BraintreeConnectionRequestType = {
      //       nango_connected: true,
      //     };
      //     const request_data: PaymentProcessorConnectionRequestType = {
      //       payment_processor: "braintree",
      //       data: inner_data,
      //     };

      //     PaymentProcessorIntegration.connectPaymentProcessor(request_data)
      //       .then((data: PaymentProcessorConnectionResponseType) => {
      //         toast.success(data.details);
      //       })
      //       .catch((error) => {
      //         toast.error(error.details);
      //       });
      //     refetch();
      //   })
      //   .catch((error) => {
      //     const inner_data: BraintreeConnectionRequestType = {
      //       nango_connected: true,
      //     };
      //     const request_data: PaymentProcessorConnectionRequestType = {
      //       payment_processor: "braintree",
      //       data: inner_data,
      //     };
      //     PaymentProcessorIntegration.connectPaymentProcessor(request_data)
      //       .then((data: PaymentProcessorConnectionResponseType) => {
      //         toast.success(data.details);
      //         refetch();
      //       })
      //       .catch((inner_error) => {
      //         toast.error(
      //           `There was an error in the OAuth flow for integration: ${error.message}`
      //         );
      //       });
      //   });
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
                title={
                  integrationsMap[item.payment_provider_name].name +
                  (item.payment_provider_name === "braintree" ? " (Beta)" : "")
                }
                description={
                  integrationsMap[item.payment_provider_name].description
                }
                icon={integrationsMap[item.payment_provider_name].icon}
                handleClickConnect={() =>
                  handleConnectWithPaymentProcessorClick(item)
                }
                selfHosted={item.self_hosted}
                idName={
                  integrationsMap[item.payment_provider_name].account_id_name
                }
                idValue={item.account_id}
                working={item.working}
              />
            </Col>
          ))}
        <Col span={6} className="h-full">
          <AppCard
            connected={false}
            title="Snowflake"
            description="Sync your data to your Snowflake warehouse"
            icon={integrationsMap.snowflake.icon}
            handleClickConnect={() =>
              navigate("/settings/integrations/snowflake")
            }
          />
        </Col>
        <Col span={6} className="h-full">
          <AppCard
            connected={false}
            title="Salesforce"
            description="Sync your products, customers, and invoices to Salesforce"
            icon={integrationsMap.salesforce.icon}
            handleClickConnect={() =>
              navigate("/settings/integrations/snowflake")
            }
          />
        </Col>
        <Col span={6} className="h-full">
          <AppCard
            connected={true}
            title="Netsuite"
            idValue="not_necessary"
            description="Sync your invoices + products to Netsuite"
            icon={integrationsMap.netsuite.icon}
            working={true}
            handleClickConnect={() => {}}
          />
        </Col>
      </Row>
      <Divider />
    </div>
  );
};
export default IntegrationsTab;
