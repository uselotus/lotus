/* eslint-disable no-shadow */
/* eslint-disable camelcase */
import React, { FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col } from "antd";
import Nango from "@nangohq/frontend";
import { toast } from "react-toastify";
import {
  PaymentProcessorIntegration,
  Organization,
  CRM,
} from "../../../../api/api";
import {
  PaymentProcessorStatusType,
  integrationsMap,
  PaymentProcessorConnectionRequestType,
  BraintreeConnectionRequestType,
  PaymentProcessorConnectionResponseType,
} from "../../../../types/payment-processor-type";
import {
  CRMConnectionStatus,
  CRMProviderType,
  CRMSetting,
} from "../../../../types/crm-types";

import { AppCard } from "../components/AppCard";
import useGlobalStore from "../../../../stores/useGlobalstore";
import { useVesselLink } from "@vesselapi/react-vessel-link";

const IntegrationsTab: FC = () => {
  const navigate = useNavigate();

  const { data, refetch } = useQuery<PaymentProcessorStatusType[]>(
    ["PaymentProcessorIntegration"],
    () =>
      PaymentProcessorIntegration.getPaymentProcessorConnectionStatus().then(
        (res) => res
      )
  );

  const {
    data: crmData,
    isLoading: crmLoading,
    refetch: refetchCrm,
  } = useQuery<CRMConnectionStatus[]>(["CRMIntegration"], () =>
    CRM.getCRMConnectionStatus().then((res) => res)
  );

  const {
    data: linkToken,
    isLoading: linkTokenLoading,
    refetch: refetchLinkToken,
  } = useQuery<string | undefined>(["CRMProviderLinkToken"], () =>
    CRM.getLinkToken()
      .then((res) => res.link_token)
      .catch((err) => undefined)
  );

  const org = useGlobalStore((state) => state.org);

  const nango = new Nango({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    publicKey: (import.meta as any).env.VITE_NANGO_PK,
    debug: true,
  }); // Nango Cloud

  const { open } = useVesselLink({
    onSuccess: (publicToken) =>
      CRM.storePublicToken(publicToken)
        .then((response) => {
          if (response?.success) {
            refetchCrm();
            toast.success("Successfully connected to Salesforce");
          } else {
            toast.error("Failed to connect to Salesforce");
          }
        })
        .catch((error) => {
          toast.error("Failed to connect to Salesforce");
        }),
    onClose: () => console.log("closed"),
    onLoad: () => console.log("loaded"),
  });

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
      let unique_config_key = "";
      if (this_org?.organization_type.toLowerCase() === "production") {
        toast.error("Braintree is not supported in production environment.");
        return;
      }
      unique_config_key = "braintree-sandbox";
      nango
        .auth(unique_config_key, item.connection_id)
        .then((result) => {
          toast.success(
            `OAuth flow succeeded for provider "${result.providerConfigKey}"!`
          );
          const inner_data: BraintreeConnectionRequestType = {
            nango_connected: true,
          };
          const request_data: PaymentProcessorConnectionRequestType = {
            payment_processor: "braintree",
            data: inner_data,
          };

          PaymentProcessorIntegration.connectPaymentProcessor(request_data)
            .then((data: PaymentProcessorConnectionResponseType) => {
              toast.success(data.details);
            })
            .catch((error) => {
              toast.error(error.details);
            });
          refetch();
        })
        .catch((error) => {
          const inner_data: BraintreeConnectionRequestType = {
            nango_connected: true,
          };
          const request_data: PaymentProcessorConnectionRequestType = {
            payment_processor: "braintree",
            data: inner_data,
          };
          PaymentProcessorIntegration.connectPaymentProcessor(request_data)
            .then((data: PaymentProcessorConnectionResponseType) => {
              toast.success(data.details);
              refetch();
            })
            .catch(() => {
              toast.error(
                `There was an error in the OAuth flow for integration: ${error.message}`
              );
            });
        });
    }
  };

  return (
    <div>
      <Typography.Title level={2}>Integrations</Typography.Title>
      <Row gutter={[24, 24]} className="flex items-stretch">
        {data &&
          data !== undefined &&
          data.map((item) => (
            <Col span={6} key={item.payment_provider_name}>
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
                hasAccess
              />
            </Col>
          ))}
        {crmData &&
          crmData !== undefined &&
          crmData.map((crmItem, index) => (
            <Col span={6} key={index}>
              <AppCard
                connected={crmItem.connected}
                title={
                  integrationsMap[crmItem.crm_provider_name.toLowerCase()].name
                }
                description={
                  integrationsMap[crmItem.crm_provider_name.toLowerCase()]
                    .description
                }
                selfHosted={crmItem.self_hosted}
                idName={
                  integrationsMap[crmItem.crm_provider_name.toLowerCase()]
                    .account_id_name
                }
                idValue={crmItem.account_id}
                icon={
                  integrationsMap[crmItem.crm_provider_name.toLowerCase()].icon
                }
                handleClickConnect={() => {
                  if (linkToken) {
                    open({
                      integrationId: crmItem.crm_provider_name.toLowerCase(),
                      linkToken: linkToken,
                    });
                  } else {
                    toast.error(
                      `Failed to connect to ${
                        integrationsMap[crmItem.crm_provider_name.toLowerCase()]
                          .name
                      }!`
                    );
                  }
                }}
                hasAccess={org?.crm_integration_allowed || false}
                working={crmItem.working}
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
            hasAccess={false}
          />
        </Col>
        <Col span={6} className="h-full">
          <AppCard
            connected={true}
            title="Netsuite"
            idValue="not_necessary"
            description="Sync your invoices + products to Netsuite"
            icon={integrationsMap.netsuite.icon}
            working
            handleClickConnect={() => {
              //
            }}
            hasAccess={true}
          />
        </Col>
        <Col span={6} className="h-full">
          <AppCard
            connected={false}
            title="Segment"
            description="Send Usage Events From Segment to Lotus"
            icon={integrationsMap.segment.icon}
            handleClickConnect={() =>
              navigate("/settings/integrations/snowflake")
            }
            hasAccess={false}
          />
        </Col>
      </Row>
      <Divider />
    </div>
  );
};
export default IntegrationsTab;
