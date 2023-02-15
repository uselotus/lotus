import React, { FC, useState } from "react";
import { useQuery } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col, Modal, Input } from "antd";
import { PaymentProcessorIntegration, Organization } from "../../../../api/api";
import {
  PaymentProcessorStatusType,
  integrationsMap,
  PaymentProcessorType,
} from "../../../../types/payment-processor-type";
import { AppCard } from "../components/AppCard";
import useGlobalStore from "../../../../stores/useGlobalstore";
import { toast } from "react-toastify";
import Nango from "@nangohq/frontend";

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
  const [connectionId, setConnectionId] = useState("");
  const [connectionIdName, setConnectionIdName] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [paymentProcessor, setPaymentProvider] =
    useState<PaymentProcessorType | null>(null);
  var nango = new Nango({ publicKey: (import.meta as any).env.VITE_NANGO_PK }); // Nango Cloud

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
        unique_config_key = "test-btree-sbox";
      }
      nango
        .auth(unique_config_key, item.connection_id)
        .then((result) => {
          toast.success(
            `OAuth flow succeeded for provider "${result.providerConfigKey}"!`
          );
          Organization.updateOrganizationPaymentProvider({
            org_id: org.organization_id,
            payment_provider: item.payment_provider_name,
            payment_provider_id: result.connectionId,
            nango_connected: true,
          });
          refetch();
        })
        .catch((error) => {
          toast.error(
            `There was an error in the OAuth flow for integration: ${error.message}`
          );
        });
    }
  };

  const handleUpdatePaymentProviderId = () => {
    if (paymentProcessor !== null && connectionId !== "") {
      Organization.updateOrganizationPaymentProvider({
        org_id: org.organization_id,
        payment_provider: paymentProcessor,
        payment_provider_id: connectionId,
      })
        .then((res) => {
          setShowModal(false);
          setConnectionId("");
          toast.success(`${connectionIdName} updated successfully.`);
          refetch();
        })
        .catch((err) => {
          toast.error("Something went wrong.");
        });
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
                  integrationsMap[item.payment_provider_name].connection_id_name
                }
                idValue={item.connection_id}
                working={item.working}
                handleClickId={() => {
                  if (item.self_hosted === false) {
                    setShowModal(true);
                    setConnectionIdName(
                      integrationsMap[item.payment_provider_name]
                        .connection_id_name
                    );
                    setPaymentProvider(item.payment_provider_name);
                  }
                }}
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
      </Row>
      <Divider />
      {showModal && (
        <Modal
          title={`Enter ${connectionIdName}`}
          onOk={handleUpdatePaymentProviderId}
          onCancel={() => setShowModal(false)}
          visible={showModal}
        >
          <Input
            value={connectionId}
            onChange={(e) => setConnectionId(e.target.value)}
          />
        </Modal>
      )}
    </div>
  );
};
export default IntegrationsTab;
